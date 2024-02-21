# -*- coding: utf-8 -*-
"""
Controller for accessing Google Sheets API
"""
import http
import json
from typing import *

from flask import Blueprint, jsonify, request, Response
from googlesheet import GoogleSheets

flask_controller = Blueprint('googlesheets_controller', __name__)


class SheetRequest:
    account_name: str
    sheet_range: str
    keys_seq: Optional[str]
    include_first_row: bool
    break_if_na: bool
    values_mode: bool
    decorate_keys: Optional[bool]
    column_filter: dict


@flask_controller.route('/google/sheets/<string:identifier>/<string:sheet>', methods=['GET', 'POST'])
def google_sheets(identifier: str, sheet: str) -> 'flask.Response':
    if not request:
        return ''

    params = SheetRequest
    params.account_name = request.args.get('account', 'default')

    # Checking authorization
    if params.account_name.isalnum():
        try:
            with open(f'accounts/{params.account_name}.auth.json', 'r') as f:
                available_auths = json.load(f)
                if 'Authorization' not in available_auths:
                    return ''  # Wrong structure of json auth-file
                request_auth = request.headers.get('Authorization')
                if request_auth not in available_auths.get('Authorization'):
                    return Response('Not authorized', status=401)
        except FileNotFoundError:
            pass  # No authorization required for this account
        except json.decoder.JSONDecodeError:  # Malformed json auth-file
            return ''
    else:
        return ''  # account name must contain only alfanumeric

    cell_range = request.args.get('range', GoogleSheets.DEFAULT_RANGE)
    params.sheet_range = f'{sheet}!{cell_range}'
    params.keys_seq = request.args.get('keys_seq', None)
    params.include_first_row = request.args.get('include_first_row', False)
    params.break_if_na = request.args.get('break_if_na', False)
    params.values_mode = request.args.get('values_mode', False)
    params.decorate_keys = request.args.get('decorate_keys', None)

    params.column_filter = {}
    for k, v in request.args.items():
        if k.startswith('filter_'):
            params.column_filter[k[7:]] = v

    if request.method == http.HTTPMethod.GET:
        return get_range(identifier, params)
    if request.method == http.HTTPMethod.POST:
        payload = request.get_data().decode('utf-8')
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
                return set_range(identifier, data, params)
            except ValueError:
                pass  # ok, not a json
    return ''


def get_range(
        gsheet_identifier: str,
        params: Type['SheetRequest']
) -> 'flask.Response':
    """
    Outputs spreadsheet as dict/json
    :return: json
    """

    dict_mode = not params.values_mode
    gs = GoogleSheets(service_account=params.account_name)
    try:
        result = gs.get_range(
            gsheet_identifier,
            sheet_range=params.sheet_range,
            dict_mode=dict_mode,
            include_first_row=params.include_first_row,
            break_if_na=params.break_if_na,
            column_filter=params.column_filter
        )
        return jsonify(result)

    except RuntimeError as re:
        return jsonify({'error': 'Sheet is not shared with service account'})


def set_range(
        gsheet_identifier: str,
        data: Union[list, dict],
        params: Type['SheetRequest']
) -> 'flask.Response':
    """
    Sets range of spreadsheet with values,

    self.data can be:
    1. [ [], [] ]
    2. { 'a': [], 'b': [] }
    3. [ {'a': val, 'b': val}, { ... } ]
    4. empty []

    :return: answer from Google Sheets
    """

    gs = GoogleSheets(scope_type='readwrite', service_account=params.account_name)

    # We need to convert data to [ [],  [] ]
    # so, first we are checking format of data
    data_format = None

    if isinstance(data, list):
        if all([isinstance(z, list) for z in data]):  # (1)
            data_format = '[[]]'
        if all([isinstance(z, dict) for z in data]):  # (3)
            data_format = '[{}]'
        if len(data) == 0:
            data_format = '[0]'  # (4)
    elif isinstance(data, dict):
        if all([isinstance(z, list) for z in data.values()]):  # (2)
            data_format = '{[]}'

    def be_my_columns(cols: List[str], check_len: bool = True) -> List[str]:
        """ allow to use custom defined keys sequence """
        if params.keys_seq:
            keys_seq = [x.strip() for x in params.keys_seq.split(',')]  # "a, b" -> ["a", "b"]
            if (len(cols) == len(keys_seq) or check_len is False) \
                    and all([y in cols for y in keys_seq]):  # all of keys_seq are real keys
                cols = keys_seq
        return cols

    def beautiful_columns(cols: List[str], decorate: bool = False) -> List[str]:
        if decorate:
            return [x.replace('_', ' ').upper() for x in cols]
        return cols

    data_to_set = None
    if data_format:  # we must convert data to format like (1)
        if data_format == '[[]]':
            data_to_set = data  # no transform need, but can not use custom keys seq
        if data_format == '[{}]':
            data_to_set = []

            # we must check all rows, and to find all keys of {} from []
            columns: List[str] = []
            for r in data:
                row_columns = be_my_columns(r.keys(), check_len=False)
                if columns:
                    for x in row_columns:
                        if x not in columns:
                            columns.append(x)
                else:
                    columns = list(row_columns)

            data_to_set.append(
                beautiful_columns(columns, params.decorate_keys)
            )
            for element in data:
                sublist = []
                for column in columns:
                    sublist.append(element.get(column, None))
                data_to_set.append(sublist)
        if data_format == '{[]}':  # now rows limited to length of list under first key
            data_to_set = []
            columns = be_my_columns(list(data.keys()))
            data_to_set.append(
                beautiful_columns(columns, params.decorate_keys)
            )
            for i in range(len(data[columns[0]])):
                sublist = []
                for column in columns:
                    sublist.append(data[column][i])
                data_to_set.append(sublist)
        if data_format == '[0]':  # used to clear sheet
            data_to_set = []

    if data_to_set is None:
        return jsonify({'error': 'data is not in good format'})

    try:
        if len(data) > 0:
            result = gs.set_range(gsheet_identifier, data_to_set, params.sheet_range)
        else:
            result = gs.clear_range(gsheet_identifier, params.sheet_range)
        return jsonify(result)
    except RuntimeError:
        return jsonify({'error': 'Sheet is not shared with service account'} )
