#!/usr/bin/env python3

import os
import argparse
import re
import subprocess
import json
# import semver
from collections import defaultdict

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
    exit_code = os.system(cmd)
    if not ignoreError and exit_code != 0:
        print('!!! Command \'' + cmd + '\' exited with: ' + str(exit_code))
        exit(-1)
    return exit_code

def execAndGetOutput(cmd):
    output = subprocess.check_output(cmd, shell=True)
    return output.decode('utf-8')

def execAndParseJson(cmd):
    output = execAndGetOutput(cmd)
    return json.loads(output)

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
    if url.count('/') <= 1:
        url = 'docker.io/' + url
    if url.startswith('docker.io/'):
        url = 'index.' + url
    if not url.startswith('docker://'):
        url = 'docker://' + url
    return url


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
        ('-rc' + v['rc'] + '.ce.' + v['ce'] if v['rc'] and v['ce'] else '') + \
        ('-rc' + v['rc'] if v['rc'] and not v['ce'] else '') + \
        ('-ce.' + v['ce'] if not v['rc'] and v['ce'] else '') + \
        (v['rest'] or '')


def compare_version(v1, v2):
    if not v1 and not v2:
        return 0
    if not v1:
        return -1
    if not v2:
        return 1

    if not v1['rest'] == v2['rest'] \
        or (v1['ce'] and not v2['ce']) \
        or (not v1['ce'] and v2['ce']):
        print('!!! cannot compare versions ' + str_version(v1) + ' and ' + str_version(v2))
        exit(-1)

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

    if v1['ce'] and v2['ce']:
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


src_image = to_full_image_url(args.src)
print('>>> Read source tags for', src_image)
inspectJson = execAndParseJson('skopeo inspect ' + src_image)
src_tags = inspectJson['RepoTags']
# src_tags = ['14.10.2', '14.10.3', '14.10', '14.11.1', '13.14.0', '13', '13-rc1-alpine', '13-rc2-alpine']
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
print('>>> Read destination tags for', dest_image)
inspectJson = execAndParseJson('skopeo inspect ' + dest_image)
dest_tags = inspectJson['RepoTags']
# dest_tags = ['14.10.2', '14.10.3', '14.10', '14.11.1', '13.14.0', '13']
dest_tags = [t for t in dest_tags if parse_version(t)]


def mirror_image_tag(tag, dest_tag=None):
    # default_platform = {
    #     'os': 'linux',
    #     'architecture': 'amd64',
    # }

    src_image_tag = src_image + ':' + tag
    dest_image_tag = dest_image + ':' + tag
    if dest_tag:
        dest_image_tag = dest_image + ':' + dest_tag
    # print('>>> Read source platforms for', src_image_tag)
    # inspectJson = execAndParseJson('skopeo inspect --raw ' + src_image_tag)
    # if 'manifests' in inspectJson:
    #     platforms = [m['platform'] for m in inspectJson['manifests'] if 'platform' in m]
    # else:
    #     platforms = []
    # if len(platforms) <= 0:
    #     print('>>> No platforms found in manifest, try get it from image')
    #     inspectJson = execAndParseJson('skopeo inspect ' + src_image_tag)
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
    print('>>> Copy image tag from', src_image_tag, 'to', dest_image_tag)
    exec('skopeo copy --all ' + src_image_tag + ' ' + dest_image_tag)

print('New calculated tags are:')
for dest_tag in src_tags_latest.keys():
    print('- ' + dest_tag + ' \t-> ' + src_tags_latest[dest_tag])

if not args.no_copy:
    # mirror all existing tags
    for src_tag in [str_version(t) for t in src_tags]:
        if not args.only_new_tags or not src_tag in dest_tags:
            mirror_image_tag(src_tag)

    for dest_tag in src_tags_latest.keys():
        mirror_image_tag(src_tags_latest[dest_tag], dest_tag)
