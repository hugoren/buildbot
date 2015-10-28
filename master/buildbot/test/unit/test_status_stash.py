# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from buildbot.process.properties import Interpolate
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.status.status_stash import StashStatusPush, INPROGRESS, SUCCESSFUL, FAILED
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.util import logging
from json import loads
from mock import patch
from twisted.internet import defer
from twisted.trial import unittest
from twisted.web.http_headers import Headers


@patch.object(StashStatusPush, 'send')
class TestStashStatusPush(unittest.TestCase, logging.LoggingMixin):

    def setUp(self):
        super(TestStashStatusPush, self).setUp()

        self.setUpLogging()
        self.build = FakeBuild()
        self.status = StashStatusPush('fake host', 'fake user', 'fake password')

    def tearDown(self):
        pass

    def test_buildStarted_sends_inprogress(self, mock_send):
        """
        buildStarted should send INPROGRESS
        """
        self.status.buildStarted('fakeBuilderName', self.build)
        mock_send.assert_called_with('fakeBuilderName', self.build, INPROGRESS)

    def test_buildFinished_sends_successful_on_success(self, mock_send):
        """
        buildFinished should send SUCCESSFUL if called with SUCCESS
        """
        self.status.buildFinished('fakeBuilderName', self.build, SUCCESS)
        mock_send.assert_called_with('fakeBuilderName', self.build, SUCCESSFUL)

    def test_buildFinished_sends_failed_on_failure(self, mock_send):
        """
        buildFinished should send FAILED if called with anything other than SUCCESS
        """
        self.status.buildFinished('fakeBuilderName', self.build, FAILURE)
        mock_send.assert_called_with('fakeBuilderName', self.build, FAILED)


@patch.object(StashStatusPush, '_send')
class TestStashStatusSend(unittest.TestCase, logging.LoggingMixin):

    def setUp(self):
        super(TestStashStatusSend, self).setUp()

        self.setUpLogging()
        self.build = FakeBuild()
        self.build.builder.status.getURLForThing.return_value = 'fake_build_url'
        self.my_key_format = '%(builderName)s-%(branch)s'
        self.my_name_format = '%(builderName)s-%(branch)s-%(buildNumber)s'
        self.status = StashStatusPush('fake host', 'fake user', 'fake password',
                                      key_format=self.my_key_format,
                                      name_format=self.my_name_format)
        self.status._sha = Interpolate('fake_sha')
        self.status._branch = Interpolate('fake_branch')
        self.status._buildnumber = Interpolate('fake_buildNumber')

    @defer.inlineCallbacks
    def test_send(self, mock_send):
        d = yield self.status.send('fakeBuilderName', self.build, INPROGRESS)
        self.assertEqual(1, mock_send.call_count)
        args, kwargs = mock_send.call_args
        self.assertEqual({}, kwargs)
        self.assertEqual(3, len(args))
        request_kwargs, body, error_message = args
        self.assertEqual('fake host/rest/build-status/1.0/commits/fake_sha',
                         request_kwargs.get('uri', 'No uri present'))
        self.assertEqual('POST', request_kwargs.get('method', 'No method present'))
        headers = request_kwargs.get('headers', {})
        self.assertEqual(Headers({
                 'content-type': ['application/json; charset=utf-8'],
                 'accept-language': ['en-US, en;q=0.8'],
                 'authorization': ['Basic ZmFrZSB1c2VyOmZha2UgcGFzc3dvcmQ='],
                 'accept': ['*/*']
            }), request_kwargs.get('headers', 'No headers present'))
        try:
            body_dict = loads(body)
        except ValueError, e:
            self.fail('body is not JSON: %s' % e)
        self.assertEqual({
                'url': 'fake_build_url',
                'state': 'INPROGRESS',
                'name': 'fakeBuilderName-fake_branch-fake_buildNumber',
                'key': 'fakeBuilderName-fake_branch'
            }, body_dict)
