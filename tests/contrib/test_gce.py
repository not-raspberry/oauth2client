# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for oauth2client.contrib.gce."""

import json
from six.moves import http_client
from six.moves import urllib
import unittest

import mock

from oauth2client._helpers import _to_bytes
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import Credentials
from oauth2client.client import save_to_well_known_file
from oauth2client.contrib.gce import _SCOPES_WARNING
from oauth2client.contrib.gce import AppAssertionCredentials


__author__ = 'jcgregorio@google.com (Joe Gregorio)'


class AppAssertionCredentialsTests(unittest.TestCase):

    def test_constructor(self):
        credentials = AppAssertionCredentials(foo='bar')
        self.assertEqual(credentials.scope, '')
        self.assertEqual(credentials.kwargs, {'foo': 'bar'})
        self.assertEqual(credentials.assertion_type, None)

    @mock.patch('warnings.warn')
    def test_constructor_with_scopes(self, warn_mock):
        scope = 'http://example.com/a http://example.com/b'
        scopes = scope.split()
        credentials = AppAssertionCredentials(scope=scopes, foo='bar')
        self.assertEqual(credentials.scope, scope)
        self.assertEqual(credentials.kwargs, {'foo': 'bar'})
        self.assertEqual(credentials.assertion_type, None)
        warn_mock.assert_called_once_with(_SCOPES_WARNING)

    def test_to_json_and_from_json(self):
        credentials = AppAssertionCredentials()
        json = credentials.to_json()
        credentials_from_json = Credentials.new_from_json(json)
        self.assertEqual(credentials.access_token,
                         credentials_from_json.access_token)

    def _refresh_success_helper(self, bytes_response=False):
        access_token = u'this-is-a-token'
        return_val = json.dumps({u'access_token': access_token})
        if bytes_response:
            return_val = _to_bytes(return_val)
        http = mock.MagicMock()
        http.request = mock.MagicMock(
            return_value=(mock.Mock(status=http_client.OK), return_val))

        credentials = AppAssertionCredentials()
        self.assertEquals(None, credentials.access_token)
        credentials.refresh(http)
        self.assertEquals(access_token, credentials.access_token)

        base_metadata_uri = (
            'http://metadata.google.internal/computeMetadata/v1/instance/'
            'service-accounts/default/token')
        http.request.assert_called_once_with(
            base_metadata_uri, headers={'Metadata-Flavor': 'Google'})

    def test_refresh_success(self):
        self._refresh_success_helper(bytes_response=False)

    def test_refresh_success_bytes(self):
        self._refresh_success_helper(bytes_response=True)

    def test_refresh_failure_bad_json(self):
        http = mock.MagicMock()
        content = '{BADJSON'
        http.request = mock.MagicMock(
            return_value=(mock.Mock(status=http_client.OK), content))

        credentials = AppAssertionCredentials()
        self.assertRaises(AccessTokenRefreshError, credentials.refresh, http)

    def test_refresh_failure_400(self):
        http = mock.MagicMock()
        content = '{}'
        http.request = mock.MagicMock(
            return_value=(mock.Mock(status=http_client.BAD_REQUEST), content))

        credentials = AppAssertionCredentials()
        exception_caught = None
        try:
            credentials.refresh(http)
        except AccessTokenRefreshError as exc:
            exception_caught = exc

        self.assertNotEqual(exception_caught, None)
        self.assertEqual(str(exception_caught), content)

    def test_refresh_failure_404(self):
        http = mock.MagicMock()
        content = '{}'
        http.request = mock.MagicMock(
            return_value=(mock.Mock(status=http_client.NOT_FOUND), content))

        credentials = AppAssertionCredentials()
        exception_caught = None
        try:
            credentials.refresh(http)
        except AccessTokenRefreshError as exc:
            exception_caught = exc

        self.assertNotEqual(exception_caught, None)
        expanded_content = content + (' This can occur if a VM was created'
                                      ' with no service account or scopes.')
        self.assertEqual(str(exception_caught), expanded_content)

    def test_serialization_data(self):
        credentials = AppAssertionCredentials()
        self.assertRaises(NotImplementedError, getattr,
                          credentials, 'serialization_data')

    def test_create_scoped_required_without_scopes(self):
        credentials = AppAssertionCredentials()
        self.assertFalse(credentials.create_scoped_required())

    @mock.patch('warnings.warn')
    def test_create_scoped_required_with_scopes(self, warn_mock):
        credentials = AppAssertionCredentials(['dummy_scope'])
        self.assertFalse(credentials.create_scoped_required())
        warn_mock.assert_called_once_with(_SCOPES_WARNING)

    @mock.patch('warnings.warn')
    def test_create_scoped(self, warn_mock):
        credentials = AppAssertionCredentials()
        new_credentials = credentials.create_scoped(['dummy_scope'])
        self.assertNotEqual(credentials, new_credentials)
        self.assertTrue(isinstance(new_credentials, AppAssertionCredentials))
        self.assertEqual('dummy_scope', new_credentials.scope)
        warn_mock.assert_called_once_with(_SCOPES_WARNING)

    def test_get_access_token(self):
        http = mock.MagicMock()
        http.request = mock.MagicMock(
            return_value=(mock.Mock(status=http_client.OK),
                          '{"access_token": "this-is-a-token"}'))

        credentials = AppAssertionCredentials()
        token = credentials.get_access_token(http=http)
        self.assertEqual('this-is-a-token', token.access_token)
        self.assertEqual(None, token.expires_in)

        http.request.assert_called_once_with(
            'http://metadata.google.internal/computeMetadata/v1/instance/'
            'service-accounts/default/token',
            headers={'Metadata-Flavor': 'Google'})

    def test_save_to_well_known_file(self):
        import os
        ORIGINAL_ISDIR = os.path.isdir
        try:
            os.path.isdir = lambda path: True
            credentials = AppAssertionCredentials()
            self.assertRaises(NotImplementedError, save_to_well_known_file,
                              credentials)
        finally:
            os.path.isdir = ORIGINAL_ISDIR


if __name__ == '__main__':  # pragma: NO COVER
    unittest.main()
