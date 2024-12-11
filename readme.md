# GSheet-Jsonify

This script renders Google Sheets page as JSON content.

You must create service account in Google Cloud Project and share Google Sheet with account's email:
https://console.cloud.google.com/iam-admin/serviceaccounts

Place service account JSON file to ``accounts`` folder as ``default.json``.
If you are going to use several service accounts to access Sheets, use any alfanumeric filenames, 
and add &account=name to the request.

To add more security, file ``account.auth.json`` could be placed next to ``account.json`` with structure:
```json
{
  "Authorization": [
    "demo-bearer1",
    "demo-bearer2"
  ]
}
```
If security file exists for the chosen account, header with one of the listed bearers
``{"Authorization": "demo-bearer1"}`` must be added to
GET and POST requests to the service, otherwise request will fail with 401 status.

## Reading Google Sheet

URL of Google Sheets document looks like this:
https://docs.google.com/spreadsheets/d/1S2OmeRan3domLet4Ter5s/edit#gid=0

In this example, ``1S2OmeRan3domLet4Ter5s`` is the identifier of the Google Sheets document.
Document contains one or more Sheets (tabs) inside.
To access the document, it must be shared with service account.


Imagine we have Sheets Document like this:
```
+-----------+-------------+
| Column 1  | Column two  |
+-----------+-------------+
| value A2  | value B2    |
+-----------+-------------+
| value A3  | value B3    |
+-----------+-------------+
```

In general case:
```
GET https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1
```
table is rendered as list of dicts. This is a default mode.
```json
[
  {
    "column_1": "value A2",
    "column_two": "value B2"
  },
  {
    "column_1": "value A3",
    "column_two": "value B3"
  }
]
```


To render table as values, add ``values_mode=true`` parameter
```
GET https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1?values_mode=true
```
```json
[
  ["Column 1", "Column two"],
  ["value A2", "value B2"],
  ["value A3", "value B3"]
]
```

- In default mode, first row is used as a header, and values in the columns are translated into keys:
  - Value is lowercased.
  - Then all characters except latin characters, digits and underscore "_" are removed.
  - If resulting keys from the first row are not unique, values like "column1", "column2" used instead.
- To use service account, add parameter ``account=name``, and ``name.json`` and ``name.auth.json`` will be used
- Default range is "A1:ZZ10000". To use other range, add parameter like ``range=A1:B2``

**TODO**: describe ``include_first_row`` and ``break_if_na`` parameters


You may use filters.
Add one or more parameters with prefix "filter_" and the name of the column, like
```
GET https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1?&filter_column_1=value%20A2
```
```json
[
  {
    "column_1": "value A2",
    "column_two": "value B2"
  }
]
```

## Writing Google Sheet

Imagine we want to create table like in example for reading:
```
+-----------+-------------+
| Column 1  | Column two  |
+-----------+-------------+
| value A2  | value B2    |
+-----------+-------------+
| value A3  | value B3    |
+-----------+-------------+
```

### Values mode
We can POST data like list of lists:
```
POST https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1

[
  ["Column 1", "Column two"],
  ["value A2", "value B2"],
  ["value A3", "value B3"]
]
```
Result is being proxied from Google Sheets API:
```json
{
    "spreadsheetId": "1S2OmeRan3domLet4Ter5s",
    "updatedCells": 6,
    "updatedColumns": 2,
    "updatedRange": "Sheet5!A1:B3",
    "updatedRows": 3
}
```

### Dict mode
We can POST data as list of dicts 
```
POST https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1
[
  {
    "column_1": "value A2",
    "column_two": "value B2"
  },
  {
    "column_1": "value A3",
    "column_two": "value B3"
  }
]
```
Response from the API is the same.

For dict mode, there are two options:
- Use ``keys_seq=column_1,column_two`` to set exact order of columns. Without this parameter order is not determined.
- With ``decorate_keys=true`` parameter, header will be "COLUMN 1" and "COLUMN TWO": values are converted to upper case, and underscore is replaced with space.


### Column mode
We can fill Sheet by columns, POST with a dict of lists:
```
POST https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1
{
  "column_1": ["value A2", "value A3"],
  "column_two": ["value B2", "value B3"]
}
```
You can use parameters ``keys_seq`` and ``decorate_keys`` work in this mode.


### Clear mode
To clear sheet data (default range is A1:ZZ10000) POST:
```
POST https://servicename.xyz/google/sheets/1S2OmeRan3domLet4Ter5s/Sheet1
[]
```
To clear exact columns and rows, use "range" parameter.
