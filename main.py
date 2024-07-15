import argparse
import json

import pandas as pd
import requests
from environs import Env
from tqdm import tqdm

from utils import (collect_entry_data, fetch_query, find_next_link,
                   format_article_string_std, get_quota_info,
                   load_filter_phrases, parse_cite_score,
                   parse_document_record, sjr_parse_max_quartile)


def main():
    env = Env()
    env.read_env()
    api_key = env.str("SCOPUS_API_KEY", "secret")

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-afid",
        "--af-id",
        help="id организации для поиска по аффилированным с ней авторам.",
        type=int,
    )
    arg_parser.add_argument(
        "-y",
        "--year",
        help="Год публикации.",
        type=int,
    )
    arg_parser.add_argument(
        "-rq",
        "--raw-query",
        help="Запрос с использованием синтаксиса поиска scopus.",
        type=str,
        default="",
    )
    arg_parser.add_argument(
        "-mf",
        "--max-fetch",
        help="Ограничение на кол-во загружаемых результатов поиска.",
        type=int,
    )
    arg_parser.add_argument(
        "-rf",
        "--result-file",
        help="Имя файла c расширением xlsx для сохранения результата.",
        type=str,
        default="result.xlsx",
    )
    arg_parser.add_argument(
        "-fpf",
        "--filter-phrases-file",
        help="Файл с фразами для фильтрации по тексту о финансировании.",
        type=str,
    )
    args = arg_parser.parse_args()

    filter_phrases = []
    if args.filter_phrases_file is not None:
        filter_phrases = load_filter_phrases(args.filter_phrases_file)
    print(filter_phrases)

    af_id = f"AF-ID({args.af_id})" if args.af_id is not None else ""
    year_search = f"PUBYEAR = {args.year}" if args.year is not None else ""
    query_params = [args.raw_query, af_id, year_search]
    query_params = [param for param in query_params if param != ""]

    if not query_params:
        print("Запрос не может быть пустым.")
        exit()

    save_file_name = args.result_file

    scopus_query = " AND ".join(query_params)
    print(scopus_query)

    search_resp = fetch_query(scopus_query, api_key)
    if not search_resp.ok:
        if search_resp.status_code == 400:
            print("Ошибка, некорректный запрос.")
            exit()
        if search_resp.status_code == 401:
            print("Ошибка, проверьте наличие API Key.")
            exit()
        if search_resp.status_code == 429:
            print("Квота исчерпана.")
            exit()
        print("Другая ошибка.")
        exit()

    # with open("json_data.json", "w") as outfile:
    #     json.dump(search_resp.json(), outfile)

    search_results = search_resp.json()["search-results"]
    print(f"Всего найдено: {search_results['opensearch:totalResults']}")
    if int(search_results["opensearch:totalResults"]) == 0:
        exit()

    data = []
    page_count = 1
    results_count = 0
    run_fetch = True

    while run_fetch:
        print(f"Start process page {page_count}")
        entries = search_results["entry"]

        for entry in tqdm(entries):
            entry_data = collect_entry_data(entry)

            issn = entry.get("prism:issn", entry.get("prism:eIssn", ""))
            cite_score = parse_cite_score(issn, api_key)
            quartile = sjr_parse_max_quartile(issn)

            doc_rec_data = parse_document_record(entry_data["doc_rec_link"])
            # Пропускаем если не пустой фин. текст и нет ни одного попадания искомой фразы (при наличии таковых)
            # if (
            #         (
            #                 filter_phrases
            #                 and doc_rec_data['funding_text']
            #                 and not any([phrase in doc_rec_data['funding_text'] for phrase in filter_phrases])
            #         )
            #         or not doc_rec_data['funding_text']
            # ):
            #     continue
            cited_by_count = (
                int(entry_data["citedby_count"]) if entry_data["citedby_count"] else 0
            )
            data.append(
                [
                    entry_data["doc_rec_link"],
                    entry_data["scopus_id"],
                    entry_data["doi"],
                    entry_data["eid"],
                    entry_data["subtypeDescription"],
                    cite_score,
                    quartile,
                    entry_data["year"],
                    cited_by_count,
                    format_article_string_std(entry_data, doc_rec_data["authors"]),
                    ", ".join(doc_rec_data["authors"]),
                    entry_data["title"],
                    entry_data["journal"],
                    doc_rec_data["funding_text"],
                ]
            )
            results_count += 1

            if args.max_fetch is not None:
                if results_count >= args.max_fetch:
                    run_fetch = False
                    break

        next_link = find_next_link(search_results["link"])
        if run_fetch and next_link is not None:
            search_resp = requests.get(url=next_link)
            search_results = search_resp.json()["search-results"]
            page_count += 1
        else:
            break
    report_cols = [
        "page_link",
        "scopus_id",
        "doi",
        "eid",
        "тип публикации",
        "citeScore",
        "квартиль",
        "год",
        "кол-во цитирований",
        "article full",
        "авторы",
        "название",
        "журнал",
        "текст о финансировании",
    ]

    df = pd.DataFrame(
        data=data,
        columns=report_cols,
    )
    df.index += 1
    df.to_excel(save_file_name)

    print(get_quota_info(search_resp))
    print("Done.")


if __name__ == "__main__":
    main()
