from datetime import datetime

import pandas as pd
import pytz
import requests
from requests.compat import urljoin
from bs4 import BeautifulSoup
from lxml import html


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        " AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/104.0.5112.79 Safari/537.36"
    )
}

SCOPUS_API_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"

SJR_BASE_URL = "https://www.scimagojr.com/"

CROSSREF_WORKS_API = "https://api.crossref.org/works/"

def load_filter_phrases(filename="") -> list:
    """Загрузка фраз для фильтрации по тексту о финансировании."""

    with open(filename) as file:
        return [line.strip() for line in file if not line.isspace()]


def find_next_link(links: list[dict]):
    for link_obj in links:
        if link_obj["@ref"] == "next":
            return link_obj["@href"]

    return None


def parse_document_record(url):
    """Запрашиваем и парсим некоторые сведения из страницы документа
    (обрезанная версия информации о статье)."""

    doc_rec_resp = requests.get(url=url, headers=REQUEST_HEADERS)
    doc_rec_html_tree = html.fromstring(doc_rec_resp.text)

    authors = doc_rec_html_tree.xpath(
        "//section[@id='authorlist']/ul//span[@class='previewTxt' or @class='c']/text()"
    )
    funding_text = doc_rec_html_tree.xpath('//*[@id="fundingText"]/text()')

    return {
        "authors": authors,
        "funding_text": funding_text[0] if funding_text else "",
    }


def fetch_query(scopus_query: str, api_key: str) -> requests.Response:
    """Запрос на API поиска."""

    search_query = {
        "query": scopus_query,
        # 'cursor': '"*"',
        "apiKey": api_key,
        # "view": "complete",  # не доступно без подписки
    }
    search_resp = requests.get(url=SCOPUS_API_SEARCH_URL, params=search_query)
    search_resp.raise_for_status()

    return search_resp


def collect_entry_data(entry) -> dict:
    """Парсинг всех необходимых данных статьи из словаря в удобную структуру."""

    cover_date = entry.get("prism:coverDate", "")
    cover_year = datetime.strptime(cover_date, "%Y-%m-%d").year if cover_date else ""

    scopus_id_string = entry.get("dc:identifier", "")
    _, scopus_id = scopus_id_string.split(":")

    doc_rec_link = [
        link_["@href"] for link_ in entry["link"] if link_["@ref"] == "scopus"
    ][0]

    return {
        "doc_rec_link": doc_rec_link,
        "scopus_id": scopus_id,
        "doi": entry.get("prism:doi", ""),
        "eid": entry.get("eid", ""),
        "subtypeDescription": entry.get("subtypeDescription", ""),
        "creator": entry.get("dc:creator", ""),  # only first author
        "title": entry.get("dc:title", ""),
        "journal": entry.get("prism:publicationName", ""),
        "year": cover_year,
        "vol": entry.get("prism:volume", ""),
        "issue": entry.get("prism:issueIdentifier", ""),
        "pages": entry.get("prism:pageRange", ""),
        "citedby_count": entry.get("citedby-count", ""),
    }


def format_article_string_std(entry_data: dict, authors: list) -> str:
    """Подготовка строки информации о статье в соответствии со стандартом (почти)."""

    formatted_authors = [author.replace(",", "") for author in authors]
    if len(formatted_authors) > 3:
        formatted_authors = [*formatted_authors[:3], "и др."]
    authors = ", ".join(formatted_authors)

    issue_part = f"No. {entry_data['issue']}. " if entry_data["issue"] else ""
    pages_part = f"pp. {entry_data['pages']}. " if entry_data["pages"] else ""
    return (
        f"{authors} {entry_data['title']} //\n"
        f" {entry_data['journal']}.\n"
        f" {entry_data['year']}."
        f" Vol. {entry_data['vol']}."
        f" {issue_part}{pages_part}"
        f"https://doi.org/{entry_data['doi']}"
    )


def get_quota_info(search_resp: requests.Response) -> str:
    """Информация о квоте, остатке и дате сброса."""

    reset_time = datetime.fromtimestamp(
        int(search_resp.headers["X-RateLimit-Reset"]),
        pytz.utc,
    ).strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"Квота запросов: {search_resp.headers['X-RateLimit-Limit']}\n"
        f"Остаток по квоте: {search_resp.headers['X-RateLimit-Remaining']}\n"
        f"Время обновления квоты: {reset_time} UTC\n"
    )


def parse_cite_score(issn="", api_key=""):
    """Used issn or eissn."""

    r = requests.get(
        f"http://api.elsevier.com/content/serial/title/issn/{issn}",
        params={"apiKey": api_key},
    )
    json_resp = r.json()
    try:
        score = json_resp["serial-metadata-response"]["entry"][0][
            "citeScoreYearInfoList"
        ]["citeScoreCurrentMetric"]
    except KeyError as e:
        print(e)
        return "N/A"
    return score


def sjr_search(search_string: str = "") -> requests.Response:
    return requests.get(
        f"https://www.scimagojr.com/journalsearch.php?q={search_string}"
    )


def sjr_parse_journal_page_link(search_resp: requests.Response) -> str:
    soup = BeautifulSoup(search_resp.text, "html.parser")
    search_results = soup.find_all(attrs={"class": "search_results"})
    if not search_results:
        print("No search results.")
        return None
    links = search_results[0].find_all("a")
    if not links:
        print("No journal links.")
        return None
    return links[0].get("href")  # must be only one journal by issn


def sjr_parse_q_table(journal_url_part: str) -> pd.DataFrame:
    url_ = SJR_BASE_URL + journal_url_part
    journal_page = requests.get(url_)
    soup = BeautifulSoup(journal_page.text, "html.parser")

    table_sibl = soup.find("div", attrs={"id": "svgquartiles"})
    # assert table_sibl is not None, "Can't find table."
    try:
        table = table_sibl.find_parent().find("table")
    except AttributeError as e:
        print(e)
        print("No table.")
        return None

    table_content = []
    for row in table.tbody.find_all("tr"):
        cols = row.find_all("td")
        if cols:
            table_content.append(
                [cols[0].text.strip(), cols[1].text.strip(), cols[2].text.strip()]
            )

    return pd.DataFrame(table_content, columns=["field", "year", "quart"])


def sjr_parse_max_quartile(issn: str) -> str:
    """Get current year max quartile."""

    sjr_resp = sjr_search(issn)
    journal_link = sjr_parse_journal_page_link(sjr_resp)
    if journal_link is None:
        return "N/A (no links)"
    df = sjr_parse_q_table(journal_link)
    if df is None:
        return "N/A"
    return df[df.year == df.year.max()].quart.min()


def crossref_work(doi=''):
    """Retrieve work by DOI with CrossRef API"""

    resp = requests.get(url=urljoin(CROSSREF_WORKS_API, doi))
    resp.raise_for_status()

    return resp.json()

def crossref_work_parse_authors(work_json):
    assert work_json['status'] == 'ok', "No data"

    if work_json['message'].get('author') is None:
        return ""

    return ", ".join([
        f"{author_rec.get('family', '')} {author_rec.get('given', ' ')}"
        for author_rec
        in work_json['message']['author']
    ])

def crossref_work_parse_funders(work_json):
    assert work_json['status'] == 'ok', "No data"

    if work_json['message'].get('funder') is None:
        return ""

    funds = []
    for funder_rec in work_json['message']['funder']:
        awards = funder_rec.get('award', [])
        awards_str = ""
        if awards:
            awards_str = ", ".join(awards)
        funds.append(
            f"{funder_rec.get('name', '')} {awards_str}"
        )

    return "; ".join(funds)
