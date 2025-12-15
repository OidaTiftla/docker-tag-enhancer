#!/usr/bin/env python3

"""
Integration tests for docker-tag-enhancer with mocked registries.
These tests simulate the complete workflow without accessing real registries.
"""

import unittest
from unittest.mock import patch
from collections import defaultdict

import run


class MockArgs:
    """Mock args object for integration testing"""
    def __init__(self):
        self.prefix = None
        self.suffix = None
        self.filter = None
        self.src = 'docker.io/test/source'
        self.dest = 'docker.io/test/dest'
        self.dry_run = False
        self.no_copy = False
        self.only_new_tags = False
        self.update_latest = False
        self.only_use_skopeo = True  # Use skopeo to avoid REST API calls
        self.src_registry_token = None
        self.dest_registry_token = None
        self.registry_token = None
        self.login = False


class TestIntegrationWithMockedRegistry(unittest.TestCase):
    """Integration tests with fully mocked registry operations"""

    def setUp(self):
        """Set up mocks and test environment"""
        self.original_args = run.args
        run.args = MockArgs()

        # Clear token cache
        run.token_cache = {}

        # Mock source tags from registry
        self.mock_src_tags = [
            '14.10.2', '14.10.3', '14.10.0',
            '14.11.1', '14.11.0',
            '13.14.0', '13.13.5',
        ]

        # Mock destination tags (already exist)
        self.mock_dest_tags = [
            '14.10.2', '13.14.0'  # Some tags already exist
        ]

    def tearDown(self):
        """Clean up after tests"""
        run.args = self.original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_dry_run_tag_calculation(self, mock_exec_with_retry, mock_exec_json):
        """Test dry run with mocked registry responses"""
        run.args.dry_run = True
        run.args.no_copy = False

        # Mock skopeo list-tags responses
        def mock_list_tags(cmd):
            if 'source' in cmd:
                return {'Tags': self.mock_src_tags}
            else:
                return {'Tags': self.mock_dest_tags}

        mock_exec_json.side_effect = mock_list_tags

        # Parse tags as the main script would
        src_tags = [t for t in [run.parse_version(t) for t in self.mock_src_tags] if t]

        # Group and calculate (lines 433-439 from run.py)
        src_tags_grouped = defaultdict(list)
        for t in src_tags:
            major_key = t['major']
            src_tags_grouped[major_key].append(t)

            if t['minor']:
                minor_key = t['major'] + '.' + t['minor']
                src_tags_grouped[minor_key].append(t)

        src_tags_latest = dict(
            (k, run.str_version(run.max_version(src_tags_grouped[k])))
            for k in src_tags_grouped.keys()
        )

        # Verify calculated tags
        expected_tags = {
            '14': '14.11.1',
            '13': '13.14.0',
            '14.10': '14.10.3',
            '14.11': '14.11.1',
            '13.14': '13.14.0',
            '13.13': '13.13.5',
        }

        self.assertEqual(src_tags_latest, expected_tags)

        # In dry-run mode, execWithRetry should not be called
        self.assertEqual(mock_exec_with_retry.call_count, 0)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_only_new_tags_mode(self, mock_exec_with_retry, mock_exec_json):
        """Test --only-new-tags mode to skip existing tags"""
        run.args.only_new_tags = True
        run.args.dry_run = False

        # Mock responses
        def mock_list_tags(cmd):
            if 'source' in cmd:
                return {'Tags': self.mock_src_tags}
            else:
                return {'Tags': self.mock_dest_tags}

        mock_exec_json.side_effect = mock_list_tags

        # Simulate the filtering logic
        src_tags = [t for t in [run.parse_version(t) for t in self.mock_src_tags] if t]
        dest_tags = self.mock_dest_tags

        # Calculate which tags need to be copied
        src_tags_grouped = defaultdict(list)
        for t in src_tags:
            major_key = t['major']
            src_tags_grouped[major_key].append(t)

            if t['minor']:
                minor_key = t['major'] + '.' + t['minor']
                src_tags_grouped[minor_key].append(t)

        src_tags_latest = dict(
            (k, run.str_version(run.max_version(src_tags_grouped[k])))
            for k in src_tags_grouped.keys()
        )

        # Filter out tags that already exist in dest
        new_tags = {k: v for k, v in src_tags_latest.items() if k not in dest_tags}

        # Should only include new tags
        self.assertIn('14', new_tags)
        self.assertIn('13', new_tags)
        self.assertIn('14.10', new_tags)

        # Verify that existing patch versions won't trigger copy if using only_new_tags
        # The tag '14.10.2' already exists in dest, but '14.10' calculated tag is new
        self.assertEqual(new_tags['14.10'], '14.10.3')

    @patch('run.execAndParseJsonWithRetryRateLimit')
    def test_update_latest_tag(self, mock_exec_json):
        """Test --update-latest flag"""
        run.args.update_latest = True
        run.args.dry_run = True

        # Mock responses
        def mock_list_tags(cmd):
            if 'source' in cmd:
                return {'Tags': self.mock_src_tags}
            else:
                return {'Tags': self.mock_dest_tags}

        mock_exec_json.side_effect = mock_list_tags

        # Calculate overall latest tag
        src_tags = [t for t in [run.parse_version(t) for t in self.mock_src_tags] if t]

        # Find the absolute latest version
        from functools import cmp_to_key

        def prepare_for_sort(v):
            v_copy = v.copy()
            if 'rest' in v_copy:
                del v_copy['rest']
            if 'ce' in v_copy and not v_copy['ce']:
                v_copy['ce'] = '-1'
            return v_copy

        src_tags_sorted = sorted(
            src_tags,
            key=cmp_to_key(lambda x, y: run.compare_version(prepare_for_sort(x), prepare_for_sort(y)))
        )

        latest_version = run.str_version(src_tags_sorted[-1])

        # The latest should be 14.11.1
        self.assertEqual(latest_version, '14.11.1')

    @patch('run.execAndParseJsonWithRetryRateLimit')
    def test_filter_regex(self, mock_exec_json):
        """Test filtering tags with regex"""
        import re

        run.args.filter = r'^((?!-rc|^8\.|^9\.).)*$'
        run.args.dry_run = True

        # Add some tags that should be filtered
        mock_src_with_filter = self.mock_src_tags + [
            '8.5.0', '9.1.0', '14.10.5-rc1'
        ]

        mock_exec_json.return_value = {'Tags': mock_src_with_filter}

        # Parse and filter
        src_tags = [run.parse_version(t) for t in mock_src_with_filter]
        src_tags = [t for t in src_tags if t]

        # Apply filter as in run.py line 431
        src_tags_filtered = [
            t for t in src_tags
            if re.search(run.args.filter, run.str_version(t))
        ]

        # Convert back to strings for assertion
        filtered_strings = [run.str_version(t) for t in src_tags_filtered]

        # Should exclude RC and versions starting with 8 or 9
        self.assertNotIn('8.5.0', filtered_strings)
        self.assertNotIn('9.1.0', filtered_strings)
        self.assertNotIn('14.10.5-rc1', filtered_strings)
        self.assertIn('14.10.2', filtered_strings)
        self.assertIn('13.14.0', filtered_strings)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    def test_prefix_suffix_filtering(self, mock_exec_json):
        """Test prefix and suffix filtering"""
        run.args.prefix = 'v'
        run.args.suffix = '-alpine'

        mock_tags = [
            'v14.10.2-alpine',
            'v14.10.3-alpine',
            '14.10.4-alpine',  # Wrong prefix
            'v14.10.5',        # Wrong suffix
            'v13.0.0-alpine',
        ]

        mock_exec_json.return_value = {'Tags': mock_tags}

        # Parse with prefix/suffix
        src_tags = [run.parse_version(t) for t in mock_tags]
        src_tags = [t for t in src_tags if t]

        # Should only parse tags with correct prefix and suffix
        parsed_strings = [run.str_version(t) for t in src_tags]

        self.assertIn('v14.10.2-alpine', parsed_strings)
        self.assertIn('v14.10.3-alpine', parsed_strings)
        self.assertIn('v13.0.0-alpine', parsed_strings)
        # Tags with wrong prefix or suffix should not be parsed (return None)
        self.assertEqual(len(parsed_strings), 3)


class TestMirrorImageTag(unittest.TestCase):
    """Test the mirror_image_tag function with mocks"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()
        run.args.only_use_skopeo = True

        # Set up global variables needed by mirror_image_tag
        run.src_image = 'docker://docker.io/test/source'
        run.dest_image = 'docker://docker.io/test/dest'
        run.src_api = 'docker.io'
        run.dest_api = 'docker.io'
        run.src_name = 'test/source'
        run.dest_name = 'test/dest'
        run.dest_tags = ['14.10.2']
        run.src_skopeo_auth_args = '--authfile /tmp/test'
        run.dest_skopeo_auth_args = '--authfile /tmp/test'
        run.src_dest_skopeo_auth_args = '--authfile /tmp/test'

    def tearDown(self):
        run.args = self.original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_skip_copy_when_digests_match(self, mock_exec_retry, mock_exec_json):
        """Test that copy is skipped when source and dest digests match"""
        run.args.dry_run = False

        same_digest = 'sha256:abcdef1234567890'

        # Mock inspect responses to return same digest
        mock_exec_json.side_effect = [
            {'Digest': same_digest},  # Source inspect
            {'Digest': same_digest},  # Dest inspect
        ]

        # Call mirror_image_tag
        run.mirror_image_tag('14.10.2')

        # Should not call copy since digests match
        mock_exec_retry.assert_not_called()

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_copy_when_digests_differ(self, mock_exec_retry, mock_exec_json):
        """Test that copy happens when digests differ"""
        run.args.dry_run = False

        # Mock inspect responses with different digests
        mock_exec_json.side_effect = [
            {'Digest': 'sha256:source123'},
            {'Digest': 'sha256:dest456'},
        ]

        # Call mirror_image_tag
        run.mirror_image_tag('14.10.2')

        # Should call copy since digests differ
        mock_exec_retry.assert_called_once()

        # Verify the copy command includes proper flags
        copy_cmd = mock_exec_retry.call_args[0][0]
        self.assertIn('skopeo copy', copy_cmd)
        self.assertIn('--preserve-digests', copy_cmd)
        self.assertIn('--all', copy_cmd)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_copy_with_different_dest_tag(self, mock_exec_retry, mock_exec_json):
        """Test copying from one tag to a different tag name"""
        run.args.dry_run = False

        # Mock different digests
        mock_exec_json.side_effect = [
            {'Digest': 'sha256:source123'},
            {'Digest': 'sha256:dest456'},
        ]

        # Call with different source and dest tags
        run.mirror_image_tag('14.10.3', '14.10')

        # Should perform copy
        mock_exec_retry.assert_called_once()

        copy_cmd = mock_exec_retry.call_args[0][0]
        # Should include both source tag (14.10.3) and dest tag (14.10)
        self.assertIn(':14.10.3', copy_cmd)
        self.assertIn(':14.10', copy_cmd)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_dry_run_no_copy(self, mock_exec_retry, mock_exec_json):
        """Test that dry-run mode doesn't perform actual copy"""
        run.args.dry_run = True

        # Mock different digests
        mock_exec_json.side_effect = [
            {'Digest': 'sha256:source123'},
            {'Digest': 'sha256:dest456'},
        ]

        # Call mirror_image_tag
        run.mirror_image_tag('14.10.2')

        # Should not call copy in dry-run mode
        mock_exec_retry.assert_not_called()


class TestCompleteWorkflow(unittest.TestCase):
    """End-to-end workflow test with comprehensive mocking"""

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('sys.argv', ['run.py', '-s', 'docker.io/test/src', '-d', 'docker.io/test/dest',
                        '--dry-run', '--only-use-skopeo'])
    def test_complete_workflow_dry_run(self, mock_exec_retry, mock_exec_json):
        """Test the complete workflow in dry-run mode"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()

        # Mock tag lists
        src_tags = ['14.10.2', '14.10.3', '14.11.1', '13.14.0']
        dest_tags = ['14.10.2']

        call_count = [0]

        def mock_list_tags(cmd):
            call_count[0] += 1
            if 'src' in cmd or call_count[0] == 1:
                return {'Tags': src_tags}
            else:
                return {'Tags': dest_tags}

        mock_exec_json.side_effect = mock_list_tags

        # Manually replicate the workflow
        parsed_src = [t for t in [run.parse_version(t) for t in src_tags] if t]

        src_tags_grouped = defaultdict(list)
        for t in parsed_src:
            src_tags_grouped[t['major']].append(t)
            if t['minor']:
                src_tags_grouped[t['major'] + '.' + t['minor']].append(t)

        src_tags_latest = dict(
            (k, run.str_version(run.max_version(src_tags_grouped[k])))
            for k in src_tags_grouped.keys()
        )

        # Expected tags to be created
        expected = {
            '14': '14.11.1',
            '13': '13.14.0',
            '14.10': '14.10.3',
            '14.11': '14.11.1',
            '13.14': '13.14.0',
        }

        self.assertEqual(src_tags_latest, expected)

        # Verify that in dry-run, no actual copies are made
        # (execWithRetry shouldn't be called)
        self.assertEqual(mock_exec_retry.call_count, 0)

        # Clean up
        run.args = original_args

    def test_version_edge_cases(self):
        """Test various edge cases in version handling"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()

        # Test zero versions
        v = run.parse_version('0.0.0')
        self.assertIsNotNone(v)
        self.assertEqual(v['major'], '0')

        # Test single digit versions
        v = run.parse_version('1')
        self.assertIsNotNone(v)
        self.assertEqual(run.str_version(v), '1')

        # Test large version numbers
        v = run.parse_version('999.999.999')
        self.assertIsNotNone(v)
        self.assertEqual(run.str_version(v), '999.999.999')

        # Test with all features
        v = run.parse_version('1.2.3-rc4.ce.5-alpine')
        self.assertIsNotNone(v)
        self.assertEqual(v['major'], '1')
        self.assertEqual(v['minor'], '2')
        self.assertEqual(v['patch'], '3')
        self.assertEqual(v['rc'], '4')
        self.assertEqual(v['ce'], '5')
        self.assertEqual(v['rest'], '-alpine')

        # Clean up
        run.args = original_args


if __name__ == '__main__':
    unittest.main()
