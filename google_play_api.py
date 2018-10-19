import os

import httplib2
import time
from apiclient.discovery import build
from oauth2client import tools
from oauth2client.client import flow_from_clientsecrets, OAuth2WebServerFlow, Storage
from oauth2client.service_account import ServiceAccountCredentials


class GooglePlayApi:
    """
    This class is a simplified wrapper around the google api client lib.
    """

    def __init__(self, credentials, package_name):
        http = httplib2.Http()
        http = credentials.authorize(http)
        self.edit = None
        self.package_name = package_name
        self.service = build('androidpublisher', 'v2', http=http)

    @staticmethod
    def get_credentials(options, cache_location=None):
        """
        Get credentials object needed for constructing GooglePlayAPi.
        There are a coupe of ways to get the credentials:
        - using a service
          {'service': {'json': path-to-json.json}}
          or
          {'service': {'p12': path-to-p12.p12}}
        - using oauth
          {'oauth': {'json': path-to-client-secret-json.json}}
          or
          {'oauth': {'client-id': your-client-id, 'client-secret': your-client-secret}

        :param options: the authentication options
        :param cache_location: (optional) if using oauth it'll store the credentials in a file
        :return: the credentials object
        """
        credentials = None
        flow = None

        scope = 'https://www.googleapis.com/auth/androidpublisher'
        redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'

        if 'service' in options and 'json' in options['service']:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                    options['service']['json'],
                    [scope])
        if 'service' in options and 'p12' in options['service']:
            credentials = ServiceAccountCredentials.from_p12_keyfile(
                    options['p12'],
                    [scope])
        if 'oauth' in options and 'json' in options['oauth']:
            flow = flow_from_clientsecrets(
                    options['oauth']['json'],
                    scope=scope,
                    redirect_uri=redirect_uri)
        if 'oauth' in options is True and 'client-id' in options['oauth'] and 'client-secret' in options['oauth']:
            flow = OAuth2WebServerFlow(
                    client_id=options['oauth']['client-id'],
                    client_secret=options['oauth']['client-secret'],
                    scope=scope,
                    redirect_uri=redirect_uri)

        if flow is not None:
            if cache_location is None:
                cache_location = os.path.join(os.getenv("HOME"), ".gplay", "credentials.dat")

            storage = Storage(cache_location)
            credentials = storage.get()
            if credentials is None or credentials.invalid:
                credentials = tools.run_flow(flow, storage)

        if credentials is None:
            exit(ValueError('missing credentials'))

        return credentials

    def start_edit(self):
        """
        Starts a batch operation. Calling this method more then once will invalidate the previous one.
        :return: a new Edit object
        """
        return Edit(self.service, self.package_name)

    def entitlements(self):
        """
        :return: A user's current entitlement to an inapp item or subscription.
        """
        return self.service.entitlements().list(packageName=self.package_name).execute()

    def reviews(self):
        """
        :return: list of reviews
        """
        return self.service.reviews().list(packageName=self.package_name).execute()['reviews']

    def review(self, review_id):
        """
        :param review_id: the reviewId of an item given when getting reviews list
        :return: the review
        """
        return self.service.reviews().get(packageName=self.package_name, reviewId=review_id).execute()

    def reviews_reply(self, review_id, reply):
        """
        Reply to a review
        :param review_id: the reviewId of an item given when getting reviews list
        :param reply: the content of the reply
        """
        self.service.reviews().reply(
                packageName=self.package_name, reviewId=review_id, body={u'replyText': reply}
        ).execute()


class Edit:
    """
    Starts a batch operation. All methods (except for commit) are not persisted until commit() is called.
    """

    def __init__(self, service, package_name):
        self.package_name = package_name
        self.service = service
        self.edit = service.edits().insert(body={}, packageName=self.package_name).execute()
        self.edit['created'] = time.time()

    def commit(self):
        """
        Commits and persist all changes made.
        No actions will be permanent until this method is called.
        :return: the result object
        """
        if self.edit is None:
            print 'Nothing to commit'

        result = self.service.edits().commit(editId=self.edit['id'], packageName=self.package_name).execute()

        self.edit = None

        return result

    def move_track(self, version_code, track):
        """
        Moves version from one track to another.
        Tracks can only move up: alpha -> beta -> production
        :param version_code: the version code to update
        :param track: the track to move to
        :return: the response of this action
        """
        edit_id = self.edit['id']

        return self.service.edits().tracks().update(
                editId=edit_id,
                track=track,
                packageName=self.package_name,
                body={u'versionCodes': [version_code]}
        ).execute()

    def get_versions(self):
        edit_id = self.edit['id']

        track_response = self.service.edits().tracks().list(
                editId=edit_id,
                packageName=self.package_name,
        ).execute()

        return track_response['tracks']

    def increase_rollout(self, rollout_fraction, version_code=None):
        """
        Set the roll out fraction to given package name. If no version_codes is given it
        uses the highest version code only.
        :param rollout_fraction: in range of 0.05 to 1
        :param version_code: the version code to update or None to use the latest version
        """

        edit_id = self.edit['id']

        if version_code is None:

            track_version_code = self.get_active_version_code('rollout')

            if track_version_code is None:
                raise ValueError('There are is no version available')

            version_code = track_version_code

        print 'Changing version %d to %.2f' % (version_code, rollout_fraction)

        if rollout_fraction == 1.0:
            self.move_track(version_code, 'production')
            self.move_track(None, 'rollout')
        else:
            track_response = self.service.edits().tracks().update(
                    editId=edit_id,
                    track='rollout',
                    packageName=self.package_name,
                    body={u'track': 'rollout',
                          u'userFraction': rollout_fraction,
                          u'versionCodes': [version_code]}
            ).execute()

            print 'Track %s is set for version code(s) %s' % (
                track_response['track'], str(track_response['versionCodes']))

    def get_active_version_code(self, track='production'):
        """
        Get the active version code of the given track
        :param track: either 'production', 'beta' or 'alpha' (defaults to 'production')
        :return: the version code
        """

        track_result = self.service.edits().tracks().get(
                editId=self.edit['id'], packageName=self.package_name, track=track
        ).execute()

        version_codes = track_result['versionCodes']

        if version_codes is None or len(version_codes) == 0:
            return None

        return version_codes[-1]

    def upload(self, apk_file, track='production', rollout_fraction=None):
        """
        Upload an apk file.
        :param apk_file: the path to the url file (can be max 1GB)
        :param track: either 'production', 'beta' or 'alpha' (defaults to 'production')
        :param rollout_fraction: in range of 0.05 to 1 (optional, but mandatory for 'rollout')
        :return:
        """

        if rollout_fraction is not None and track is not 'rollout':
            raise IllegalArgument('Fraction as been specified but track is not rollout')
        if rollout_fraction is None and track is 'rollout':
            raise IllegalArgument('Track "rollout" needs a rollout_fraction')

        upload_result = self.service.edits().apks().upload(
                editId=self.edit['id'],
                packageName=self.package_name,
                media_body=apk_file
        ).execute()

        version_code = upload_result['versionCode']

        print 'Version code %d has been uploaded' % version_code

        body = {u'versionCodes': [version_code]}

        if track is 'rollout':
            body[u'userFraction'] = rollout_fraction
            body[u'track'] = track

        track_response = self.service.edits().tracks().update(
                editId=self.edit['id'],
                track=track,
                packageName=self.package_name,
                body=body
        ).execute()

        print 'Track %s is set for version code(s) %s' % (
            track_response['track'], str(track_response['versionCodes']))


class IllegalArgument(Exception):
    pass
