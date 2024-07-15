## Скрипт для поиска публикаций в базе Scopus через Elsevier Scopus APIs

Скрипт использует Elsevier Scopus API (https://dev.elsevier.com/sc_apis.html) и язык запросов scopus (https://dev.elsevier.com/sc_search_tips.html) для поиска публикаций.

## Настройки

1. Зарегистрируйтесь по ссылке https://dev.elsevier.com/ и сгенерировать `API key`.

2. Создайте в каталоге со скриптом текстовый файл `.env` (без расширения) и скопируйте в него полученный ключ в формате:

```properties
SCOPUS_API_KEY=762as5f680as89d1f99sd78f6h29f89s
```
строку `762as5f680as89d1f99sd78f6h29f89s` заменить на ваш ключ.


## Установка зависимостей

1. Интерпретатор Python версии 3.9.6 или выше должен быть установлен (https://www.python.org/downloads/release/python-396/).
2. Для установки зависимостей в командной строке перейдите в каталог со скриптом и выполните команду:

```commandline
pip install -r requirements.txt
```

## Использование

Для осуществления поиска, например, по ключевым словам `machine learning` и `GNSS` составьте строку с этими словами в соответствии с синтаксисом поиска scopus: `KEY(machine learning) AND KEY(GNSS)`, далее в терминале перейти в каталог со скриптом и выполнить команду:

```commandline
python main.py -rq "KEY(machine learning) AND KEY(GNSS)" -rf results.xlsx -mf 2
```

Скрипт выполнит запрос на API для поиска по составленному запросу, ограничится двумя результатами поиска и сохранит их в файл `results.xlsx`.

Можно составить любой возможный запрос в соответствии с синтаксисом scopus search и передать его в параметр `-rq` - это основной параметр. Подробное описание синтаксиса - https://dev.elsevier.com/sc_search_tips.html

Подробная справка по параметрам вызывается командой `python main.py -h`.


## Специфический функционал

Для решения такой специфической задачи как _выгрузка всех публикаций, авторы которых аффилированы с определенной организацией_ предусмотрен более простой способ запроса данных. В нем не требуется составлять строку с ключевыми словами синтаксиса scopus, а нужно лишь указывая значения специальных параметров:

 - `-afid` - id организации для поиска по аффилированным авторам
 - `-y` - год публикации
 - `-fpf` текстовый файл с ключевыми фразами для фильтрации в тексте о финансировании

id организации (affil-id) можно узнать по адресу https://zenodo.org/record/5502475#.ZBu1PHZBxaR или в html коде страницы профиля автора аффилированного с интересующей организацией на сайте scopus
(сделать поиск в html коде по строке `/affil/profile.uri?afid=`).

Ключевые фразы должны быть заполнены в файле построчно: одна строка - одна фраза.
Например, файл `filters.txt` содержит две ключевые фразы:

```text
012-34-56789
работа выполнена с использованием ресурсов ЦКП
```

Пример запуска:

```commandline
python main.py -afid 12345678 -y 2023 -fpf filters.txt -rf results.xlsx
```

где `12345678` - id организации, `results.xlsx` - имя файла для сохранения результата.

## Примеры

```commandline
python.exe .\main.py -rq "AF-ID(60110131) AND (PUBYEAR > 2017 AND PUBYEAR < 2023)" -rf 5years.xlsx     
```
выгрузка публикаций ВЦ ДВО РАН за 5 лет: 2018-2022 гг. (60110131 - scopus af-id ВЦ ДВО РАН).

```commandline
python.exe .\main.py -rq "AU-ID(1234567890) AND (PUBYEAR > 2018)" -rf UsenName.xlsx
```

выгрузка публикаций автора с ид = 1234567890 с 2019 года и далее.

Найти scopus author id можно по адресу - https://www.scopus.com/freelookup/form/author.uri

##  Как работает скрипт?

Скрипт использует язык поисковых запросов scopus и Elsevier Scopus APIs, точнее один ресурс - `https://api.elsevier.com/content/search/scopus`.

Например, для поиска всех статей за 2023 год авторы которых аффилированы с организацией с `id=12345678`
нужно составить следующий поисковый запрос: `AF-ID(12345678) AND PUBYEAR = 2022` и далее передать его как параметр `query` в GET-запрос
на ресурс API `https://api.elsevier.com/content/search/scopus`, также необходимо добавить параметр `apiKey` с API ключом. Знак равенства `=` нужно заменить на кодированный - `%3d`

В итоге получиться:


```html
https://api.elsevier.com/content/search/scopus?query=AF-ID(12345678) AND PUBYEAR %3d 2022&apiKey=762as5f680as89d1f99sd78f6h29f89s
```

В ответе сервера будет json объект со списком найденных статей.

Данный скрипт формирует такие запросы и отправляет на сервер scopus. Полученный результат сохраняется в xlsx файл.
Подробнее про синтаксис запросов - https://dev.elsevier.com/sc_search_tips.html

Вероятно, есть риск блокировки по ip, хотя скрипт работает без VPN.


## Ограничения

Почти у всех API есть квоты. На запросы поиска статей квота составляет 20000 запросов в неделю. Подробная информация - https://dev.elsevier.com/api_key_settings.html


## Ссылки

- https://dev.elsevier.com/sc_apis.html - Elsevier Scopus APIs
- http://schema.elsevier.com/dtds/document/bkapi/search/SCOPUSSearchTips.htm - Scopus Search Guide
- https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl - Article (Full Text) Retrieval API / запрос полных текстов 
- https://dev.elsevier.com/sc_search_tips.html - Scopus Search Guide
- https://zenodo.org/record/5502475#.ZBu1PHZBxaR - Russian Index of the Research Organizations (RIRO)
- https://pybliometrics.readthedocs.io/en/stable/# - альтернативный инструмент, требует ip организации
- https://www.tutorialspoint.com/html/html_url_encoding.htm - HTML - URL Encoding
- https://scientometrics.hse.ru/seminar/ - Вебинар «Скопус после скопуса: какие функции сохранились и чем заменить выпавшие?»


## TODO

- обработка исключений - связь, апи ключ, пр.