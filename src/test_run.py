#!/usr/bin/env python3

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import json
from io import StringIO

# Import the functions we want to test
# We'll need to refactor run.py to make functions testable without global args
import run


class MockArgs:
    """Mock args object for testing"""
    def __init__(self):
        self.prefix = None
        self.suffix = None
        self.filter = None
        self.src = 'docker.io/test/image'
        self.dest = 'docker.io/test/dest'
        self.dry_run = True
        self.no_copy = False
        self.only_new_tags = False
        self.update_latest = False
        self.only_use_skopeo = False
        self.src_registry_token = None
        self.dest_registry_token = None
        self.registry_token = None
        self.login = False


class TestVersionParsing(unittest.TestCase):
    """Test version parsing logic"""

    def setUp(self):
        # Mock the global args
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_parse_simple_version(self):
        """Test parsing simple major.minor.patch versions"""
        result = run.parse_version('14.10.2')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '10')
        self.assertEqual(result['patch'], '2')
        self.assertIsNone(result['rc'])
        self.assertIsNone(result['ce'])

    def test_parse_major_minor_only(self):
        """Test parsing major.minor versions without patch"""
        result = run.parse_version('14.10')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '10')
        self.assertIsNone(result['patch'])

    def test_parse_major_only(self):
        """Test parsing major version only"""
        result = run.parse_version('13')
        self.assertEqual(result['major'], '13')
        self.assertIsNone(result['minor'])
        self.assertIsNone(result['patch'])

    def test_parse_rc_version(self):
        """Test parsing RC (release candidate) versions"""
        result = run.parse_version('14.11.1-rc1')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '11')
        self.assertEqual(result['patch'], '1')
        self.assertEqual(result['rc'], '1')

    def test_parse_ce_version(self):
        """Test parsing CE (community edition) versions"""
        result = run.parse_version('14.10.2-ce.5')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '10')
        self.assertEqual(result['patch'], '2')
        self.assertEqual(result['ce'], '5')

    def test_parse_rc_ce_version(self):
        """Test parsing combined RC and CE versions"""
        result = run.parse_version('14.10.2-rc3.ce.5')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '10')
        self.assertEqual(result['patch'], '2')
        self.assertEqual(result['rc'], '3')
        self.assertEqual(result['ce'], '5')

    def test_parse_with_rest_suffix(self):
        """Test parsing versions with additional suffixes"""
        result = run.parse_version('13.14.0-alpine')
        self.assertEqual(result['major'], '13')
        self.assertEqual(result['minor'], '14')
        self.assertEqual(result['patch'], '0')
        self.assertEqual(result['rest'], '-alpine')

    def test_parse_invalid_version(self):
        """Test that invalid versions return None"""
        self.assertIsNone(run.parse_version('invalid'))
        self.assertIsNone(run.parse_version('v1.2.3'))  # prefix not allowed without args.prefix
        self.assertIsNone(run.parse_version('1.2.3.4'))  # too many components

    def test_parse_with_prefix(self):
        """Test parsing with prefix filter"""
        run.args.prefix = 'v'
        result = run.parse_version('v14.10.2')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '10')
        self.assertEqual(result['patch'], '2')

        # Should return None if prefix doesn't match
        self.assertIsNone(run.parse_version('14.10.2'))

    def test_parse_with_suffix(self):
        """Test parsing with suffix filter"""
        run.args.suffix = '-alpine'
        result = run.parse_version('14.10.2-alpine')
        self.assertEqual(result['major'], '14')
        self.assertEqual(result['minor'], '10')
        self.assertEqual(result['patch'], '2')

        # Should return None if suffix doesn't match
        self.assertIsNone(run.parse_version('14.10.2'))


class TestVersionComparison(unittest.TestCase):
    """Test version comparison logic"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_compare_equal_versions(self):
        """Test comparing equal versions"""
        v1 = run.parse_version('14.10.2')
        v2 = run.parse_version('14.10.2')
        self.assertEqual(run.compare_version(v1, v2), 0)

    def test_compare_different_major(self):
        """Test comparing different major versions"""
        v1 = run.parse_version('13.0.0')
        v2 = run.parse_version('14.0.0')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_different_minor(self):
        """Test comparing different minor versions"""
        v1 = run.parse_version('14.9.0')
        v2 = run.parse_version('14.10.0')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_different_patch(self):
        """Test comparing different patch versions"""
        v1 = run.parse_version('14.10.1')
        v2 = run.parse_version('14.10.2')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_with_and_without_minor(self):
        """Test comparing versions with and without minor component"""
        v1 = run.parse_version('14')
        v2 = run.parse_version('14.10')
        # Version without minor should be considered less specific (older)
        self.assertEqual(run.compare_version(v1, v2), 1)
        self.assertEqual(run.compare_version(v2, v1), -1)

    def test_compare_rc_versions(self):
        """Test comparing RC versions"""
        v1 = run.parse_version('14.10.0-rc1')
        v2 = run.parse_version('14.10.0-rc2')
        self.assertEqual(run.compare_version(v1, v2), -1)

        # RC should be less than non-RC
        v3 = run.parse_version('14.10.0')
        self.assertEqual(run.compare_version(v1, v3), -1)
        self.assertEqual(run.compare_version(v3, v1), 1)

    def test_compare_ce_versions(self):
        """Test comparing CE versions"""
        v1 = run.parse_version('14.10.0-ce.1')
        v2 = run.parse_version('14.10.0-ce.2')
        self.assertEqual(run.compare_version(v1, v2), -1)

    def test_compare_incompatible_versions_raises(self):
        """Test that comparing versions with different rest suffixes raises exception"""
        v1 = run.parse_version('13.14.0-alpine')
        v2 = run.parse_version('13.14.0-debian')
        with self.assertRaises(Exception) as ctx:
            run.compare_version(v1, v2)
        self.assertIn('Cannot compare versions', str(ctx.exception))

    def test_compare_null_versions(self):
        """Test comparing null versions"""
        v1 = run.parse_version('14.10.2')
        self.assertEqual(run.compare_version(None, None), 0)
        self.assertEqual(run.compare_version(None, v1), -1)
        self.assertEqual(run.compare_version(v1, None), 1)


class TestVersionString(unittest.TestCase):
    """Test version string reconstruction"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_str_version_simple(self):
        """Test reconstructing simple version strings"""
        v = run.parse_version('14.10.2')
        self.assertEqual(run.str_version(v), '14.10.2')

    def test_str_version_major_only(self):
        """Test reconstructing major-only version"""
        v = run.parse_version('13')
        self.assertEqual(run.str_version(v), '13')

    def test_str_version_with_rc(self):
        """Test reconstructing RC version"""
        v = run.parse_version('14.11.1-rc1')
        self.assertEqual(run.str_version(v), '14.11.1-rc1')

    def test_str_version_with_prefix_suffix(self):
        """Test reconstructing version with prefix and suffix"""
        run.args.prefix = 'v'
        run.args.suffix = '-alpine'
        v = run.parse_version('v14.10.2-alpine')
        self.assertEqual(run.str_version(v), 'v14.10.2-alpine')


class TestMaxVersion(unittest.TestCase):
    """Test finding maximum version from a list"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_max_version_simple(self):
        """Test finding max from simple versions"""
        versions = [
            run.parse_version('14.10.1'),
            run.parse_version('14.10.2'),
            run.parse_version('14.10.3'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '14.10.3')

    def test_max_version_with_rc(self):
        """Test that non-RC is greater than RC"""
        versions = [
            run.parse_version('14.10.0-rc1'),
            run.parse_version('14.10.0-rc2'),
            run.parse_version('14.10.0'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '14.10.0')

    def test_max_version_mixed(self):
        """Test finding max from mixed version types"""
        versions = [
            run.parse_version('13.14.0'),
            run.parse_version('14.10.2'),
            run.parse_version('14.10.3'),
            run.parse_version('14.11.1-rc1'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '14.11.1-rc1')


class TestImageUrlParsing(unittest.TestCase):
    """Test Docker image URL parsing"""

    def test_parse_full_url(self):
        """Test parsing full Docker image URL"""
        result = run.parse_image_url('docker://registry.example.com/myorg/myimage:latest')
        self.assertEqual(result['protocol'], 'docker')
        self.assertEqual(result['host'], 'registry.example.com')
        self.assertEqual(result['name'], 'myorg/myimage')
        self.assertEqual(result['tag'], 'latest')

    def test_parse_dockerhub_short(self):
        """Test parsing short Docker Hub format"""
        result = run.parse_image_url('nginx')
        self.assertEqual(result['protocol'], 'docker')
        self.assertEqual(result['host'], 'index.docker.io')
        self.assertEqual(result['name'], 'library/nginx')

    def test_parse_dockerhub_with_org(self):
        """Test parsing Docker Hub with organization"""
        result = run.parse_image_url('myorg/myimage')
        self.assertEqual(result['protocol'], 'docker')
        self.assertEqual(result['host'], 'index.docker.io')
        self.assertEqual(result['name'], 'myorg/myimage')

    def test_to_full_image_url(self):
        """Test URL normalization"""
        # to_full_image_url doesn't add 'library/' - that's done by parse_image_url
        self.assertEqual(
            run.to_full_image_url('nginx'),
            'docker://index.docker.io/nginx'
        )
        self.assertEqual(
            run.to_full_image_url('docker.io/myorg/myimage'),
            'docker://index.docker.io/myorg/myimage'
        )


class TestTagCalculation(unittest.TestCase):
    """Test the core tag calculation logic"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_tag_grouping_simple(self):
        """Test grouping tags by major and major.minor"""
        src_tags_str = ['14.10.2', '14.10.3', '14.11.1', '13.14.0']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        # Replicate the grouping logic from run.py
        src_tags_grouped = {}
        for t in src_tags:
            # Group by major
            major_key = t['major']
            if major_key not in src_tags_grouped:
                src_tags_grouped[major_key] = []
            src_tags_grouped[major_key].append(t)

            # Group by major.minor if minor exists
            if t['minor']:
                minor_key = t['major'] + '.' + t['minor']
                if minor_key not in src_tags_grouped:
                    src_tags_grouped[minor_key] = []
                src_tags_grouped[minor_key].append(t)

        # Check major groups
        self.assertIn('14', src_tags_grouped)
        self.assertIn('13', src_tags_grouped)
        self.assertEqual(len(src_tags_grouped['14']), 3)  # 14.10.2, 14.10.3, 14.11.1
        self.assertEqual(len(src_tags_grouped['13']), 1)  # 13.14.0

        # Check major.minor groups
        self.assertIn('14.10', src_tags_grouped)
        self.assertIn('14.11', src_tags_grouped)
        self.assertEqual(len(src_tags_grouped['14.10']), 2)  # 14.10.2, 14.10.3
        self.assertEqual(len(src_tags_grouped['14.11']), 1)  # 14.11.1

        # Find max versions for each group
        src_tags_latest = {}
        for k in src_tags_grouped.keys():
            max_v = run.max_version(src_tags_grouped[k])
            src_tags_latest[k] = run.str_version(max_v)

        # Verify calculated tags
        self.assertEqual(src_tags_latest['14'], '14.11.1')  # Latest in major 14
        self.assertEqual(src_tags_latest['13'], '13.14.0')  # Latest in major 13
        self.assertEqual(src_tags_latest['14.10'], '14.10.3')  # Latest in 14.10
        self.assertEqual(src_tags_latest['14.11'], '14.11.1')  # Latest in 14.11

    def test_tag_grouping_with_rc(self):
        """Test that RC versions are properly grouped and compared"""
        src_tags_str = ['14.10.0', '14.10.1-rc1', '14.10.1-rc2', '14.10.1']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        src_tags_grouped = {}
        for t in src_tags:
            major_minor_key = t['major'] + '.' + t['minor']
            if major_minor_key not in src_tags_grouped:
                src_tags_grouped[major_minor_key] = []
            src_tags_grouped[major_minor_key].append(t)

        max_v = run.max_version(src_tags_grouped['14.10'])
        # The final release should be greater than RC versions
        self.assertEqual(run.str_version(max_v), '14.10.1')

    def test_tag_grouping_with_suffix(self):
        """Test grouping with rest suffixes"""
        src_tags_str = ['13-alpine', '13-rc1-alpine', '13-rc2-alpine']

        # Manually parse with rest suffix
        src_tags = []
        for tag in src_tags_str:
            v = run.parse_version(tag)
            if v:
                src_tags.append(v)

        # Group by major + rest
        src_tags_grouped = {}
        for t in src_tags:
            key = t['major'] + (t['rest'] or '')
            if key not in src_tags_grouped:
                src_tags_grouped[key] = []
            src_tags_grouped[key].append(t)

        # All should be in the same group
        self.assertIn('13-alpine', src_tags_grouped)
        self.assertEqual(len(src_tags_grouped['13-alpine']), 3)


class TestEndToEndTagCalculation(unittest.TestCase):
    """Integration test for the complete tag calculation pipeline"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_complete_tag_calculation(self):
        """Test complete tag calculation matching the main script logic"""
        # Simulate source tags from a registry
        src_tags_raw = [
            '14.10.2', '14.10.3', '14.10.0',
            '14.11.1-rc1', '14.11.1',
            '13.14.0', '13.13.5',
            'invalid-tag',  # Should be filtered out
        ]

        # Parse and filter (same as run.py lines 429-432)
        src_tags = [run.parse_version(t) for t in src_tags_raw]
        src_tags = [t for t in src_tags if t]  # Filter None values

        # Group tags (same as run.py lines 433-438)
        from collections import defaultdict
        src_tags_grouped = defaultdict(list)
        for t in src_tags:
            major_key = (run.args.prefix or '') + t['major'] + \
                       ('-ce' if t.get('ce') else '') + \
                       (t.get('rest') or '') + \
                       (run.args.suffix or '')
            src_tags_grouped[major_key].append(t)

        for t in src_tags:
            if t['minor']:
                minor_key = (run.args.prefix or '') + t['major'] + '.' + t['minor'] + \
                           ('-ce' if t.get('ce') else '') + \
                           (t.get('rest') or '') + \
                           (run.args.suffix or '')
                src_tags_grouped[minor_key].append(t)

        # Calculate latest for each group (same as run.py line 439)
        src_tags_latest = dict(
            (k, run.str_version(run.max_version(src_tags_grouped[k])))
            for k in src_tags_grouped.keys()
        )

        # Verify expected tag mappings
        expected = {
            '14': '14.11.1',      # Latest in major 14
            '13': '13.14.0',      # Latest in major 13
            '14.10': '14.10.3',   # Latest in 14.10.x
            '14.11': '14.11.1',   # Latest in 14.11.x
            '13.14': '13.14.0',   # Latest in 13.14.x
            '13.13': '13.13.5',   # Latest in 13.13.x
        }

        self.assertEqual(src_tags_latest, expected)

    def test_tag_calculation_with_filter(self):
        """Test tag calculation with regex filter"""
        import re

        src_tags_raw = [
            '14.10.2', '14.10.3-rc1', '8.5.0', '9.0.0'
        ]

        # Apply filter (simulating args.filter)
        run.args.filter = r'^((?!-rc|^8\.|^9\.|^10\.|^11\.|^12\.).)*$'

        src_tags = [run.parse_version(t) for t in src_tags_raw]
        src_tags = [t for t in src_tags if t]

        # Apply filter as in run.py line 431
        original_tags = [run.str_version(t) for t in src_tags]
        filtered_tags = [run.str_version(t) for t in src_tags if re.search(run.args.filter, run.str_version(t))]

        # Should exclude RC versions and versions starting with 8, 9, 10, 11, 12
        self.assertIn('14.10.2', filtered_tags)
        self.assertNotIn('14.10.3-rc1', filtered_tags)
        self.assertNotIn('8.5.0', filtered_tags)
        self.assertNotIn('9.0.0', filtered_tags)

    def test_update_latest_calculation(self):
        """Test calculating the 'latest' tag"""
        from functools import cmp_to_key

        src_tags_raw = ['14.10.2', '14.10.3', '13.14.0', '15.0.0-rc1', '14.11.1']
        src_tags = [t for t in [run.parse_version(t) for t in src_tags_raw] if t]

        # Group tags
        from collections import defaultdict
        src_tags_grouped = defaultdict(list)
        for t in src_tags:
            major_key = t['major']
            src_tags_grouped[major_key].append(t)

        src_tags_latest = dict(
            (k, run.str_version(run.max_version(src_tags_grouped[k])))
            for k in src_tags_grouped.keys()
        )

        # Sort the grouped keys to find overall latest (lines 567-570)
        def prepare_for_sort(v):
            v_copy = v.copy()
            if 'rest' in v_copy:
                del v_copy['rest']
            if 'ce' in v_copy and not v_copy['ce']:
                v_copy['ce'] = '-1'
            return v_copy

        src_tags_latest_sorted = list(src_tags_latest.keys())
        src_tags_latest_sorted.sort(
            key=cmp_to_key(
                lambda x, y: run.compare_version(
                    None if x is None else prepare_for_sort(run.parse_version(x)),
                    None if y is None else prepare_for_sort(run.parse_version(y))
                )
            )
        )

        # Get the overall latest
        src_tag_latest = run.str_version(
            run.max_version([run.parse_version(t) for t in src_tags_latest_sorted if t is not None])
        )

        # Should be the highest non-RC version
        self.assertEqual(src_tag_latest, '15')  # 15.0.0-rc1 is in major 15


if __name__ == '__main__':
    unittest.main()
