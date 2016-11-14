#!/usr/bin/python
"""Interact with Google Play services
Usage:
  gplay.py track active
    (--service-p12=FILE | --service-json=FILE | --oauth-json=FILE | (--oauth --client-id=ID --client-secret=SECRET))
    [--track=TRACK] PACKAGE_NAME
  gplay.py rollout
    (--service-p12=FILE | --service-json=FILE | --oauth-json=FILE | (--oauth --client-id=ID --client-secret=SECRET))
    [--track=TRACK] [--version-code=CODE] PACKAGE_NAME FRACTION
  gplay.py reviews
    (--service-p12=FILE | --service-json=FILE | --oauth-json=FILE | (--oauth --client-id=ID --client-secret=SECRET))
    [--review-id=ID] PACKAGE_NAME
  gplay.py entitlements
    (--service-p12=FILE | --service-json=FILE | --oauth-json=FILE | (--oauth --client-id=ID --client-secret=SECRET))
    PACKAGE_NAME
  gplay.py upload
    (--service-p12=FILE | --service-json=FILE | --oauth-json=FILE | (--oauth --client-id=ID --client-secret=SECRET))
    [--track=TRACK] [--faction=FRACTION] PACKAGE_NAME FILE

Commands:
  track active             get the active version code (defaults to 'production' track)
  rollout                  increase the rollout percentage
  reviews                  get list of reviews
  entitlements             get in app entitlements
  upload                   upload APK (defaults to 'production' track)

Options:
  --service-p12=FILE       uses a p12 file for service account credentials
  --service-json=FILE      uses a json file for service account credentials
  --oauth-json=FILE        uses a client-secret json file for oauth credentials (opens browser)
  --oauth                  uses a client-secret supplied with --client-id and --client-secret (opens browser)
  --client-id=ID
  --client-secret=SECRET

  --track=TRACK            select track (production, beta or alpha)  [default: production]
  --version-code=CODE      app version code to select [default: latest]
  --fraction=FRACTION      the percentage of users that receives this update (0.2 .. 1)

  --review-id=ID           get a single review

"""
from docopt import docopt
from google_play_api import GooglePlayApi


def rollout(api, args):
    version_code = args['--version-code'] if not 'latest' else None
    track = args['--track'] if not False else 'production'
    rollout_fraction = float(args['FRACTION'])
    edit = api.start_edit()
    edit.increase_rollout(rollout_fraction, track, version_code)
    commit_result = edit.commit_edit()
    print '(%s) Successfully rolled out to %.2f' % (commit_result['id'], rollout_fraction)


def get_active_track(api):
    edit = api.start_edit()
    print edit.get_active_version_code('production')


def get_credentials(args):

    if args['--service-json'] is not None:
        options = {'service-json': args['--service-json']}
    if args['--service-p12'] is not None:
        options = {'service-p12': args['--service-p12']}
    if args['--oauth-json'] is not None:
        options = {'oauth-json': args['--oauth-json']}
    if args['--oauth'] is True:
        options = {'oauth': {'client-id': args['--client-id'], 'client-secret': args['--client-secret']}}

    return GooglePlayApi.get_credentials(options)


def get_reviews(api, args):
    if args['--review-id'] is None:
        reviews = api.reviews()
        for review in reviews:
            print_review(review)
        print ''
    else:
        review = api.review(args['--review-id'])
        print_review(review)


def upload_apk(api, args):
    apk_file = args['FILE']
    rollout_fraction = args['--fraction'] if not False else None
    track = args['--track'] if not False else 'production'

    edit = api.start_edit()
    edit.upload(apk_file, track, rollout_fraction)
    commit_result = edit.commit_edit()
    print '(%s) Successfully uploaded apkf' % commit_result['id']


def print_review(review):
    print 'name:  %s' % review['authorName']
    print 'id:    %s' % review['reviewId']
    for comment in review['comments']:
        if 'userComment' in comment:
            user_comment = comment['userComment']
            print '- User'
            print '       (version: %s/%s, android: %s, language: %s, device: %s, starRating: %s)' % (
                user_comment['appVersionCode'],
                user_comment['appVersionName'],
                user_comment['androidOsVersion'],
                user_comment['reviewerLanguage'],
                user_comment['device'],
                user_comment['starRating'])
            print '       %s' % user_comment['text']
        elif 'developerComment' in comment:
            print '- Dev'
            print '       %s' % comment['developerComment']['text']


def do_action(args):
    package_name = args['PACKAGE_NAME']
    api = GooglePlayApi(get_credentials(args), package_name)

    if args['track'] is True and args['active'] is True:
        get_active_track(api)
        return

    if args['rollout'] is True:
        rollout(api, args)
        return

    if args['reviews'] is True:
        get_reviews(api, args)
        return

    if args['entitlements'] is True:
        print api.entitlements()
        return

    if args['upload'] is True:
        upload_apk(api, args)
        return


if __name__ == '__main__':
    do_action(docopt(__doc__, version='1.0.0'))
