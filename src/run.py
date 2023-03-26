#!/usr/bin/env python3

import argparse
import re
import sys
import subprocess
import requests
import json
# import semver
from collections import defaultdict
from functools import cmp_to_key
from time import sleep

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--src', required=True, type=str, help='The repository image to read from.')
parser.add_argument('-d', '--dest', required=True, type=str, help='The repository image to push enhanced tags to.')
parser.add_argument('-f', '--filter', type=str, help='A regex to filter the tags to process.')
parser.add_argument('--only-new-tags', action='store_true', help='Only push new tags to destination.')
parser.add_argument('--no-copy', action='store_true', help='Skip the copy operation.')
parser.add_argument('--login', action='store_true', help='Perform a login (--registry is required).')
parser.add_argument('-r', '--registry', type=str, help='The registry to login (defaults to docker.io).')

def parse_arguments():
    return parser.parse_args()


args = parse_arguments()


def exec(cmd, ignoreError=False):
    # source: https://stackoverflow.com/a/27661481
    pipes = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = pipes.communicate()
    exit_code = pipes.returncode
    std_out = std_out.decode(sys.getfilesystemencoding())
    std_err = std_err.decode(sys.getfilesystemencoding())

    if not ignoreError and exit_code != 0:
        # an error happened!
        raise Exception(exit_code, std_out, std_err)

    elif not ignoreError and len(std_err):
        # return code is 0 (no error), but we may want to
        # do something with the info on std_err
        # i.e. logger.warning(std_err)
        print('>>!', std_err)

    # do whatever you want with std_out
    return exit_code, std_out, std_err


def withRetryRateLimit(func):
    while True:
        try:
            return func()
        except KeyboardInterrupt:
            raise
        except BaseException as err:
            if len(err.args) == 3:
                exit_code, std_out, std_err = err.args
                if 'toomanyrequests' in std_err:
                    print('>>> Rate limit reached, retrying in 15min:', std_out, std_err, 'Exit code:', exit_code)
                    sleep(900)
                    continue
            raise


def withRetry(func):
    while True:
        try:
            return withRetryRateLimit(func)
        except KeyboardInterrupt:
            raise
        except BaseException as err:
            print('>>> Failed, retrying in 5min:', err)
            sleep(300)


def execWithRetryRateLimit(cmd):
    return withRetryRateLimit(lambda: exec(cmd))


def execWithRetry(cmd):
    return withRetry(lambda: exec(cmd))


def execAndParseJson(cmd):
    exit_code, std_out, std_err = exec(cmd)
    return json.loads(std_out)


def execAndParseJsonWithRetryRateLimit(cmd):
    return withRetryRateLimit(lambda: execAndParseJson(cmd))


def execAndParseJsonWithRetry(cmd):
    return withRetry(lambda: execAndParseJson(cmd))


def escapeParamSingleQuotes(param):
    return param.replace('`', '\\`').replace('\'', '\'"\'"\'')


def escapeParamDoubleQuotes(param):
    return param.replace('`', '\\`').replace('"', '"\'"\'"')


if args.login:
    registry = args.registry
    if not registry:
        registry = 'docker.io'
    if registry == 'docker.io':
        registry = 'index.' + registry
    exec('skopeo login ' + registry)
    exit(0)


def to_full_image_url(url):
    if '.' not in url:
        url = 'docker.io/' + url
    if url.startswith('docker.io/'):
        url = 'index.' + url
    if not url.startswith('docker://'):
        url = 'docker://' + url
    return url


def parse_image_url(url):
    url = to_full_image_url(url)
    m = re.search(r'^(?P<protocol>[^:]*)://(?P<host>[^/]*)/(?P<name>[^:]*)(?::(?P<tag>.*))?$', url)
    if not m:
        return None
    result = m.groupdict()
    if '/' not in result['name']:
        result['name'] = 'library/' + result['name']
    if result['name'].startswith('_/'):
        result['name'] = 'library/' + result['name'][2:]
    return result


def parse_version(text):
    m = re.search(r'^(?P<major>0|[1-9]\d*)(?:\.(?P<minor>0|[1-9]\d*)(?:\.(?P<patch>0|[1-9]\d*))?)?(-((rc(?P<rc>0|[1-9]\d*)\.)?ce\.(?P<ce>0|[1-9]\d*)|rc(?P<rc2>0|[1-9]\d*)))?(?P<rest>-.*)?$', text)
    if not m:
        return None
    result = m.groupdict()
    if result['rc2']:
        result['rc'] = result['rc2']
    del result['rc2']
    return result


def str_version(v):
    return v['major'] + \
        ('.' + v['minor'] if v['minor'] else '') + \
        ('.' + v['patch'] if v['patch'] else '') + \
        ('-rc' + v['rc'] + '.ce.' + v['ce'] if 'rc' in v and v['rc'] and 'ce' in v and v['ce'] else '') + \
        ('-rc' + v['rc'] if 'rc' in v and v['rc'] and ('ce' not in v or not v['ce']) else '') + \
        ('-ce.' + v['ce'] if ('rc' not in v or not v['rc']) and 'ce' in v and v['ce'] else '') + \
        ('rest' in v and v['rest'] or '')


def compare_version(v1, v2):
    if not v1 and not v2:
        return 0
    if not v1:
        return -1
    if not v2:
        return 1

    if ('rest' in v1 and 'rest' in v2 and not v1['rest'] == v2['rest']) \
        or ('ce' in v1 and not 'ce' in v2 and v1['ce']) \
        or (not 'ce' in v1 and 'ce' in v2 and v2['ce']) \
        or ('ce' in v1 and 'ce' in v2 and v1['ce'] and not v2['ce']) \
        or ('ce' in v1 and 'ce' in v2 and not v1['ce'] and v2['ce']):
        raise Exception('Cannot compare versions ' + str_version(v1) + ' and ' + str_version(v2))

    if int(v1['major']) < int(v2['major']):
        return -1
    elif int(v1['major']) > int(v2['major']):
        return 1

    if v1['minor'] and v2['minor']:
        if int(v1['minor']) < int(v2['minor']):
            return -1
        elif int(v1['minor']) > int(v2['minor']):
            return 1
    elif v1['minor'] and not v2['minor']:
        return -1
    elif not v1['minor'] and v2['minor']:
        return 1

    if v1['patch'] and v2['patch']:
        if int(v1['patch']) < int(v2['patch']):
            return -1
        elif int(v1['patch']) > int(v2['patch']):
            return 1
    elif v1['patch'] and not v2['patch']:
        return -1
    elif not v1['patch'] and v2['patch']:
        return 1

    if v1['rc'] and v2['rc']:
        if int(v1['rc']) < int(v2['rc']):
            return -1
        elif int(v1['rc']) > int(v2['rc']):
            return 1
    elif v1['rc'] and not v2['rc']:
        return -1
    elif not v1['rc'] and v2['rc']:
        return 1

    if 'ce' in v1 and 'ce' in v2 and v1['ce'] and v2['ce']:
        if int(v1['ce']) < int(v2['ce']):
            return -1
        elif int(v1['ce']) > int(v2['ce']):
            return 1

    # versions are equal
    return 0


def max_version(versions):
    latest = None
    for v in versions:
        if not latest:
            latest = v
            continue

        if compare_version(v, latest) > 0:
            latest = v

    return latest


def curl_get_all_from_pages_docker_hub(url):
    result = []
    while True:
        o = execAndParseJsonWithRetry('curl -sSX GET "' + url + '"')
        result += o['results']
        url = o['next']
        if not url:
            return result


DOCKER_HOSTS = [
    'index.docker.io',
    'index.docker.com',
    'registry.docker.io',
    'registry.docker.com',
    'registry-1.docker.io',
    'registry-1.docker.com',
    'docker.io',
    'docker.com',
]


token_cache = {}


def retrieve_new_token(api, scope=None):
    cache_key = api + '+' + scope

    if scope is None:
        scope = 'repository::pull,push'

    match api:
        case item if item in DOCKER_HOSTS:
            params = {
                'service': 'registry.docker.io',
                'scope': scope
            }
            url = 'https://auth.docker.io/token'
            r = requests.get(url, params=params)
            r.raise_for_status()
            o = r.json()
            token = o['token']
            token_cache[cache_key] = token
            return token

    return None


def get_or_retrieve_token(api, scope=None):
    cache_key = api + '+' + scope

    if cache_key in token_cache:
        return token_cache[cache_key]

    return retrieve_new_token(api, scope)


def request_docker_registry(api, name, pathAndQuery):
    url = 'https://' + api + '/v2/' + name + '/' + pathAndQuery
    scope = 'repository:' + name + ':pull,push'
    token = get_or_retrieve_token(api, scope)
    i = 0
    while True:
        i += 1
        headers = {}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        r = requests.get(url, headers=headers)
        if r.status_code == 401 and i == 0:
            token = retrieve_new_token(api, scope)
        else:
            break
    r.raise_for_status()
    o = r.json()
    return o['tags']


src_image = to_full_image_url(args.src)
src_url = parse_image_url(args.src)
src_host = src_url['host']
src_protocol = src_url['protocol']
src_name = src_url['name']
src_api = src_host
if src_api in DOCKER_HOSTS:
    src_api = 'registry.docker.com'

print('>>> Read source tags for', src_image)
tags = request_docker_registry(src_api, src_name, 'tags/list')
src_tags_digests = {
    x['name']: [i['digest'] for i in x['images'] if 'digest' in i] for x in tags
}
src_tags = [k for k, v in src_tags_digests.items() if len(v) > 0]
# src_tags = ['14.10.2', '14.10.3', '14.10', '14.11.1-rc', '13.14.0', '13', '13-rc1-alpine', '13-rc2-alpine']
src_tags = [t for t in src_tags if parse_version(t)]
if args.filter:
    src_tags = [t for t in src_tags if re.search(args.filter, t)]
src_tags = [parse_version(t) for t in src_tags]
src_tags_grouped = defaultdict(list)
for t in src_tags:
    src_tags_grouped[t['major'] + ('-ce' if t['ce'] else '') + (t['rest'] or '')].append(t)
for t in src_tags:
    if t['minor']:
        src_tags_grouped[t['major'] + '.' + t['minor'] + ('-ce' if t['ce'] else '') + (t['rest'] or '')].append(t)
src_tags_latest = dict((k, str_version(max_version(src_tags_grouped[k]))) for k in src_tags_grouped.keys())

dest_image = to_full_image_url(args.dest)
dest_url = parse_image_url(args.dest)
dest_host = dest_url['host']
dest_protocol = dest_url['protocol']
dest_name = dest_url['name']
dest_api = dest_host
if dest_api in DOCKER_HOSTS:
    dest_api = 'registry.docker.com'

print('>>> Read destination tags for', dest_image)
tags = request_docker_registry(dest_api, dest_name, 'tags/list')
dest_tags_digests = {
    x['name']: [i['digest'] for i in x['images'] if 'digest' in i] for x in tags
}
dest_tags = [k for k, v in dest_tags_digests.items() if len(v) > 0]
# dest_tags = ['14.10.2', '14.10.3', '14.10', '14.11.1', '13.14.0', '13']
dest_tags = [t for t in dest_tags if parse_version(t)]


def mirror_image_tag(tag, dest_tag=None):
    # default_platform = {
    #     'os': 'linux',
    #     'architecture': 'amd64',
    # }

    src_tag = tag
    dest_tag = (dest_tag or tag)
    src_image_tag = src_image + ':' + src_tag
    dest_image_tag = dest_image + ':' + dest_tag
    # print('>>> Read source platforms for', src_image_tag)
    # inspectJson = execAndParseJsonWithRetry('skopeo inspect --raw ' + src_image_tag)
    # if 'manifests' in inspectJson:
    #     platforms = [m['platform'] for m in inspectJson['manifests'] if 'platform' in m]
    # else:
    #     platforms = []
    # if len(platforms) <= 0:
    #     print('>>> No platforms found in manifest, try get it from image')
    #     inspectJson = execAndParseJsonWithRetry('skopeo inspect ' + src_image_tag)
    #     if 'Architecture' in inspectJson:
    #         default_platform['architecture'] = inspectJson['Architecture']
    #     if 'Os' in inspectJson:
    #         default_platform['os'] = inspectJson['Os']
    #     platforms.append(default_platform)

    # for p in platforms:
    #     opts = ''
    #     if 'os' in p:
    #         opts += ' --override-os=' + p['os']
    #     if 'architecture' in p:
    #         opts += ' --override-arch=' + p['architecture']
    #     if 'variant' in p:
    #         opts += ' --override-variant=' + p['variant']
    #     print('>>> Copy image tag from', src_image_tag, 'to', dest_image_tag, '[options:' + opts + ']')
    #     exec('skopeo' + opts + ' copy ' + src_image_tag + ' ' + dest_image_tag)
    #     exit(-1)

    src_digest = src_tags_digests[src_tag]
    dest_digest = dest_tags_digests[dest_tag] if dest_tag in dest_tags_digests else None
    if src_digest == dest_digest:
        print('>>> Image tag is already up to date (digests are equal)', dest_image_tag)
    else:
        print('>>> Copy image tag from', src_image_tag, 'to', dest_image_tag)
        execWithRetry('skopeo copy --all ' + src_image_tag + ' ' + dest_image_tag)


def copy_with_exclude(o, exclude):
    return {
        k: o[k] for k in o.keys() if k not in exclude
    }


def prepare_for_sort(v):
    v = copy_with_exclude(v, ['rest'])
    if 'ce' in v and not v['ce']:
        v['ce'] = '-1'
    return v


src_tags_sorted = [t for t in src_tags]
src_tags_sorted.sort(key=cmp_to_key(lambda x, y: compare_version(prepare_for_sort(x), prepare_for_sort(y))))
src_tags_latest_sorted = [t for t in src_tags_latest.keys()]
src_tags_latest_sorted.sort(key=cmp_to_key(lambda x, y: compare_version(None if x is None else prepare_for_sort(parse_version(x)), None if y is None else prepare_for_sort(parse_version(y)))))

print('New calculated tags are:')
for dest_tag in src_tags_latest_sorted:
    print('- ' + dest_tag + ' \t-> ' + src_tags_latest[dest_tag])

if not args.no_copy:
    # mirror all existing tags
    for src_tag in [str_version(t) for t in src_tags_sorted]:
        if not args.only_new_tags or not src_tag in dest_tags:
            mirror_image_tag(src_tag)

    for dest_tag in src_tags_latest_sorted:
        if not args.only_new_tags or not dest_tag in dest_tags:
            mirror_image_tag(src_tags_latest[dest_tag], dest_tag)
