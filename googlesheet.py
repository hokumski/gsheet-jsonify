# -*- coding: utf-8 -*-
"""
API client for Google Discovery
API client for Google Sheets v.4
"""

import os.path
import string
from typing import *
from googleapiclient import discovery
from googleapiclient.http import HttpError
from google.oauth2 import service_account


def get_google_credentials(
        scopes: List = None,
        service_account_name: str = None
) -> Optional['google.oauth2.service_account.Credentials']:
    """
    :param scopes: list of scopes
    :param service_account_name: name of service account file, without '.json' extension, 'default' if None
    :return: google credentials from service_account
    """
    if not scopes:
        scopes = []
    if not service_account_name:
        service_account_name = 'default'

    # To disable walking directories,
    if '.' in service_account_name or '/' in service_account_name or '\\' in service_account_name:
        return None

    account_path = os.path.join('accounts', f'{service_account_name}.json')
    try:
        return service_account.Credentials.from_service_account_file(account_path, scopes=scopes)
    except FileNotFoundError:
        pass
    return None


class GoogleDiscovery(object):

    _client = None

    def __init__(
            self,
            service_account_name: str,
            scopes: List[str],
            service_name: str,
            service_version: str
    ):
        credentials = get_google_credentials(scopes, service_account_name)
        # under very strange circumstances, static discovery (default option) fails to work
        # since 2021-03-04; locally it's OK, but fails on GCE
        # so, we've forced to set this parameter to False, non-default option
        self._client = discovery.build(service_name, service_version, credentials=credentials, static_discovery=False)

    @property
    def client(self):
        return self._client


class GoogleSheets(GoogleDiscovery):

    DEFAULT_RANGE = 'A1:ZZ10000'

    def __init__(
            self,
            scope_type: str = 'readonly',
            service_account: Optional[str] = None
    ):
        """
        Initializes google discovery service for Sheets v4
        :param scope_type: readonly | readwrite
        """

        scopes = []
        if scope_type == 'readonly':
            scopes.append('https://www.googleapis.com/auth/spreadsheets.readonly')
        if scope_type == 'readwrite':
            scopes.append('https://www.googleapis.com/auth/spreadsheets')

        GoogleDiscovery.__init__(self, service_account, scopes, 'sheets', 'v4')

    def get_range(
            self,
            spreadsheet: str,
            sheet_range: Optional[str] = None,
            dict_mode: bool = False,
            include_first_row: bool = False,
            break_if_na: bool = False,
            column_filter: Optional[dict] = None
    ) -> Union[List[List], List[Dict]]:
        """
        Returns values of spreadsheet from range

        :param spreadsheet: google spreadsheet id
        :param sheet_range: range in A1 notation, like Sheet1!A5:B8
        :param dict_mode: return as list of dicts
        :param include_first_row: in dict_mode, add copy of first row (with exact names)
        :param break_if_na: in dict_mode, stop adding rows to output, if any cell contains "#N/A" text
        :param column_filter: in dict_mode, if filter is given, result will be filtered by these column values

        :return: values as list of lists, [ ['a', 'b'], ['1', '2'] ] or as list of dicts [ {'a':'1', 'b': '2'} ]

        :raises RuntimeError if not authorized (sheet not shared with service account)
        """
        if not sheet_range:
            sheet_range = GoogleSheets.DEFAULT_RANGE

        answer = None
        try:
            answer = self.client.spreadsheets().values().get(
                spreadsheetId=spreadsheet,
                range=sheet_range
            ).execute()
        except HttpError:
            raise RuntimeError('Not authorized to get values from this spreadsheet')

        if isinstance(answer, dict) and answer.get('values', None):
            if dict_mode:
                return GoogleSheets._get_as_list_of_dicts(
                    range_result_values=answer['values'],
                    include_first_row=include_first_row,
                    break_if_na=break_if_na,
                    column_filter=column_filter
                )
            values = answer['values']  # waiting for [ [],[],...]
            if isinstance(values, list):
                max_length = max([len(x) for x in values if isinstance(x, list)])
                for i in range(len(values)):
                    if isinstance(values[i], list) and len(values[i]) < max_length:
                        # adding empty values to the end of line
                        values[i].extend([''] * (max_length - len(values[i])))
            return values
        return []

    @staticmethod
    def _get_as_list_of_dicts(
            range_result_values: List,
            generate_names: bool = True,
            include_first_row: bool = False,
            break_if_na: bool = False,
            column_filter: Optional[dict] = None
    ) -> Optional[List[Dict]]:
        """
        Converts result of get_range to [{}, {}, ... ]

        :param range_result_values: result of get_range
        :param generate_names: if True, trying to convert first to row into dict names,
        {"column1": ..., "column2": ....} if False
        :param include_first_row: when True, add exact header values as first row
        :param break_if_na: when True, stop iteration if row contains "#N/A"
        :param column_filter: in dict_mode, if filter is given, result will be filtered by these column values
        :return: list of dicts
        """

        def good_names(row: List[str]) -> List[str]:
            """
            :param row: sample row like ['unique name', 'Hello, World!']
            :return: like ['unique_name', 'hello_world']
            """
            allow_letters = '_' + string.ascii_lowercase + string.digits
            row = [x.lower().replace(' ', '_') for x in row]
            result = [''.join([c for c in w if c in allow_letters]) for w in row]
            if len(set(result)) == len(row):  # because all names must be unique
                return result
            return columnx(row)  # "variant B"

        def columnx(row: Union[List[str], int]) -> List[str]:
            """
            :param row: sample row (we need only len)
            :return: ['column1', 'column2', ...]
            :raise ValueError
            """
            if isinstance(row, list):
                return [f'column{x + 1}' for x in range(len(row))]
            if isinstance(row, int):
                return [f'column{x + 1}' for x in range(row)]
            raise ValueError('row param must be list or int')

        if isinstance(range_result_values, list):
            names = []
            result = []
            # not possible to generate names from single row
            # this means, there is no actual result

            skip_first_row = False
            if generate_names and len(range_result_values) > 1:
                names = good_names(range_result_values[0])
                if not include_first_row:
                    skip_first_row = True
            else:
                names = columnx(range_result_values[0])

            for row in range_result_values:
                if skip_first_row:
                    skip_first_row = False
                    continue
                if break_if_na and '#N/A' in row:
                    break
                subresult = {}
                for i in range(len(names)):
                    try:
                        subresult[names[i]] = row[i]
                    except IndexError:  # happens when row in sheet contains NULL on last cells
                        subresult[names[i]] = None
                result.append(subresult)

            if column_filter:
                filtered = []
                for row in result:
                    matched = True
                    for k, v in column_filter.items():
                        if row[k] != v:
                            matched = False
                    if matched:
                        filtered.append(row)
                result = filtered
            return result
        return None

    def set_range(
            self,
            spreadsheet: str,
            values: List[List],
            sheet_range: Optional[str] = None,
            mode: str = None
    ):
        """
        Sets range of spreadsheet with values

        :param spreadsheet: google spreadsheet id
        :param sheet_range: range in A1 notation, like Sheet1!A5:B8
        :param values: as list of lists, [ ['a', 'b'], ['1', '2'] ]
        :param mode: valueInputOption, USER_ENTERED if None

        :return: answer from Google Sheets

        :raises RuntimeError if not authorized (not shared with)
        """

        if not sheet_range:
            sheet_range = GoogleSheets.DEFAULT_RANGE

        value_input_option = 'USER_ENTERED' if not mode else mode
        value_range_body = {
            'range': sheet_range,
            'majorDimension': 'ROWS',
            'values': values
        }

        answer = None
        try:
            answer = self.client.spreadsheets().values().update(
                spreadsheetId=spreadsheet,
                range=sheet_range,
                body=value_range_body,
                valueInputOption=value_input_option
            ).execute()
        except HttpError:
            raise RuntimeError('Not authorized to set range for this spreadsheet')

        return answer

    def clear_range(
            self,
            spreadsheet: str,
            sheet_range: Optional[str] = None
    ):
        """
        Clears range of spreadsheet

        :param spreadsheet: google spreadsheet id
        :param sheet_range: range in A1 notation, like Sheet1!A5:B8
        :return: answer from google

        :raises RuntimeError if not authorized (not shared with)
        """
        if not sheet_range:
            sheet_range = GoogleSheets.DEFAULT_RANGE

        answer = None
        try:
            answer = self.client.spreadsheets().values().clear(
                spreadsheetId=spreadsheet,
                range=sheet_range,
                body={}
            ).execute()
        except HttpError:
            raise RuntimeError('Not authorized to set (clear) range for this spreadsheet')

        return answer
