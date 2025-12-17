#!/usr/bin/env python3

"""
Integration tests for docker-tag-enhancer with mocked registries.
These tests simulate the complete workflow without accessing real registries.
"""

import unittest
from unittest.mock import patch

import run


class MockArgs:
    """Mock args object for integration testing"""
    def __init__(self):
        self.prefix = None
        self.suffix = None
        self.filter = None
        self.tag_cleanup_patterns = None
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
        self.inverse_specificity_order = False
        self.verbose = 0


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
    @patch('builtins.print')
    def test_dry_run_tag_calculation(self, mock_print, mock_exec_with_retry, mock_exec_json):
        """Test dry run with mocked registry responses"""
        run.args.dry_run = True
        run.args.no_copy = False

        # Mock skopeo responses: list-tags and inspect
        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': self.mock_src_tags}
                else:
                    return {'Tags': self.mock_dest_tags}
            elif 'inspect' in cmd:
                # Mock digest responses for image comparison
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Actually call the implementation
        run.run_main_logic()

        # Verify skopeo was called (list-tags + inspect calls)
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Check that calculated tags are printed
        self.assertIn("call('- 14 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 13 \\t-> 13.14.0')", printed_output)
        self.assertIn("call('- 14.10 \\t-> 14.10.3')", printed_output)
        self.assertIn("call('- 14.11 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 13.14 \\t-> 13.14.0')", printed_output)
        self.assertIn("call('- 13.13 \\t-> 13.13.5')", printed_output)

        # In dry-run mode, execWithRetry should not be called
        self.assertEqual(mock_exec_with_retry.call_count, 0)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    def test_only_new_tags_mode(self, mock_exec_with_retry, mock_exec_json):
        """Test --only-new-tags mode to skip existing tags"""
        run.args.only_new_tags = True
        run.args.dry_run = False

        # Mock skopeo responses
        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': self.mock_src_tags}
                else:
                    return {'Tags': self.mock_dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # With only_new_tags=True, should skip tags that already exist in dest
        # Check that execWithRetry was called, but not for tags already in dest
        exec_calls = [str(call) for call in mock_exec_with_retry.call_args_list]

        # Should NOT copy 14.10.2 or 13.14.0 (they already exist in dest)
        # Should copy new calculated tags like '14', '14.10', etc.
        for call in exec_calls:
            # Verify we're not copying tags that already exist
            if '14.10.2' in call and 'dest:14.10.2' in call:
                self.fail('Should not copy 14.10.2 as it already exists in dest')
            if '13.14.0' in call and 'dest:13.14.0' in call:
                self.fail('Should not copy 13.14.0 as it already exists in dest')

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('builtins.print')
    def test_update_latest_tag(self, mock_print, mock_exec_json):
        """Test --update-latest flag"""
        run.args.update_latest = True
        run.args.dry_run = True

        # Mock skopeo responses
        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': self.mock_src_tags}
                else:
                    return {'Tags': self.mock_dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify the output includes the 'latest' tag mapping
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # The latest should be 14.11.1 (highest version)
        self.assertIn("call('- latest \\t-> 14.11.1')", printed_output)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('builtins.print')
    def test_filter_regex(self, mock_print, mock_exec_json):
        """Test filtering tags with regex"""
        run.args.filter = r'^((?!-rc|^8\.|^9\.).)*$'
        run.args.dry_run = True

        # Add some tags that should be filtered
        mock_src_with_filter = self.mock_src_tags + [
            '8.5.0', '9.1.0', '14.10.5-rc1'
        ]

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': mock_src_with_filter}
                else:
                    return {'Tags': self.mock_dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Check the output to verify filtered tags
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should exclude RC and versions starting with 8 or 9
        self.assertNotIn('8.5.0', printed_output)
        self.assertNotIn('9.1.0', printed_output)
        self.assertNotIn('14.10.5-rc1', printed_output)
        # Should include valid tags
        self.assertIn("call('- 14 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 14.10 \\t-> 14.10.3')", printed_output)
        self.assertIn("call('- 13 \\t-> 13.14.0')", printed_output)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('builtins.print')
    def test_prefix_suffix_filtering(self, mock_print, mock_exec_json):
        """Test prefix and suffix filtering"""
        run.args.prefix = 'v'
        run.args.suffix = '-alpine'
        run.args.dry_run = True

        mock_tags = [
            'v14.10.2-alpine',
            'v14.10.3-alpine',
            '14.10.4-alpine',  # Wrong prefix
            'v14.10.5',        # Wrong suffix
            'v13.0.0-alpine',
        ]

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': mock_tags}
                else:
                    return {'Tags': []}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Check the output to verify only tags with correct prefix/suffix were processed
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should only process tags with correct prefix and suffix
        self.assertIn("call('- v14-alpine \\t-> v14.10.3-alpine')", printed_output)
        self.assertIn("call('- v14.10-alpine \\t-> v14.10.3-alpine')", printed_output)
        self.assertIn("call('- v13-alpine \\t-> v13.0.0-alpine')", printed_output)
        # Should not process tags with wrong prefix/suffix
        self.assertNotIn('14.10.4', printed_output)
        self.assertNotIn('v14.10.5', printed_output)


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
        run.mirror_image_tag('aaa', 'bbb')

        # Should perform copy
        mock_exec_retry.assert_called_once()

        copy_cmd = mock_exec_retry.call_args[0][0]
        # Should include both source tag (aaa) and dest tag (bbb)
        self.assertIn(':aaa', copy_cmd)
        self.assertIn(':bbb', copy_cmd)

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
    @patch('builtins.print')
    def test_complete_workflow_dry_run(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test the complete workflow in dry-run mode"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()
        run.args.dry_run = True

        # Mock tag lists
        src_tags = ['14.10.2', '14.10.3', '14.11.1', '13.14.0']
        dest_tags = ['14.10.2']

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should show calculated tags
        self.assertIn("call('- 14 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 14.11 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 14.10 \\t-> 14.10.3')", printed_output)
        self.assertIn("call('- 13 \\t-> 13.14.0')", printed_output)
        self.assertIn("call('- 13.14 \\t-> 13.14.0')", printed_output)

        # Verify that in dry-run, no actual copies are made
        # (execWithRetry shouldn't be called)
        self.assertEqual(mock_exec_retry.call_count, 0)

        # Clean up
        run.args = original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_complete_workflow_4part_versions(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test complete workflow with 4-part versions"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()
        run.args.dry_run = True

        # Mock tag lists with 4-part versions
        src_tags = ['7.14.10.2', '7.14.10.3', '7.14.11.1', '7.13.14.0']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify the output contains expected 4-part version tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should show calculated tags at all levels
        self.assertIn("call('- 7 \\t-> 7.14.11.1')", printed_output)
        self.assertIn("call('- 7.14 \\t-> 7.14.11.1')", printed_output)
        self.assertIn("call('- 7.13 \\t-> 7.13.14.0')", printed_output)
        self.assertIn("call('- 7.14.10 \\t-> 7.14.10.3')", printed_output)
        self.assertIn("call('- 7.14.11 \\t-> 7.14.11.1')", printed_output)
        self.assertIn("call('- 7.13.14 \\t-> 7.13.14.0')", printed_output)

        # Verify that in dry-run, no actual copies are made
        self.assertEqual(mock_exec_retry.call_count, 0)

        # Clean up
        run.args = original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_complete_workflow_5part_versions(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test complete workflow with 5-part versions"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()
        run.args.dry_run = True

        # Mock tag lists with 5-part versions
        src_tags = ['2.7.14.10.2', '2.7.14.10.3', '2.7.14.11.1', '2.7.13.14.0']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify the output contains expected 5-part version tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should show calculated tags at all levels
        self.assertIn("call('- 2 \\t-> 2.7.14.11.1')", printed_output)
        self.assertIn("call('- 2.7 \\t-> 2.7.14.11.1')", printed_output)
        self.assertIn("call('- 2.7.14 \\t-> 2.7.14.11.1')", printed_output)
        self.assertIn("call('- 2.7.13 \\t-> 2.7.13.14.0')", printed_output)
        self.assertIn("call('- 2.7.14.10 \\t-> 2.7.14.10.3')", printed_output)
        self.assertIn("call('- 2.7.14.11 \\t-> 2.7.14.11.1')", printed_output)
        self.assertIn("call('- 2.7.13.14 \\t-> 2.7.13.14.0')", printed_output)

        # Verify that in dry-run, no actual copies are made
        self.assertEqual(mock_exec_retry.call_count, 0)

        # Clean up
        run.args = original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_complete_workflow_mixed_parts(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test complete workflow with mixed 3, 4, and 5-part versions"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()
        run.args.dry_run = True

        # Mock tag lists with mixed version parts
        src_tags = ['14.10.2', '14.10.2.1', '14.10.2.1.5', '14.11.1', '14.11.1.0']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should show calculated tags
        # Remember: 3-part > 4-part > 5-part when base is the same (less specific is "greater")
        self.assertIn("call('- 14 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 14.10 \\t-> 14.10.2')", printed_output)  # 3-part is "greater" than 4-part and 5-part
        self.assertIn("call('- 14.11 \\t-> 14.11.1')", printed_output)  # 3-part is "greater" than 4-part

        # Verify that in dry-run, no actual copies are made
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
        self.assertEqual(v['parts'], ['0', '0', '0'])

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
        self.assertEqual(v['parts'], ['1', '2', '3'])
        self.assertEqual(v['rc'], '4')
        self.assertEqual(v['ce'], '5')
        self.assertEqual(v['rest'], '-alpine')

        # Clean up
        run.args = original_args


class TestInverseSpecificityOrderIntegration(unittest.TestCase):
    """Integration tests for inverse specificity order flag"""

    def setUp(self):
        """Set up test environment"""
        self.original_args = run.args
        run.args = MockArgs()

        # Clear token cache
        run.token_cache = {}

    def tearDown(self):
        """Clean up after tests"""
        run.args = self.original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_inverse_order_mixed_parts(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test complete workflow with inverse specificity order and mixed parts"""

        # Set up args
        run.args.dry_run = True
        run.args.inverse_specificity_order = True

        # Mock tag lists with mixed version parts
        # Same tags as test_complete_workflow_mixed_parts but with inverse order
        src_tags = ['14.10.2', '14.10.2.1', '14.10.2.1.5', '14.11.1', '14.11.1.0']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Expected tags for mixed versions with inverse order
        # With inverse: 5-part > 4-part > 3-part when base is the same (more specific is "greater")
        self.assertIn("call('- 14 \\t-> 14.11.1.0')", printed_output)  # 4-part is "greater" than 3-part
        self.assertIn("call('- 14.11 \\t-> 14.11.1.0')", printed_output)  # 4-part is "greater" than 3-part
        self.assertIn("call('- 14.11.1 \\t-> 14.11.1.0')", printed_output)  # 4-part is "greater" than 3-part
        self.assertIn("call('- 14.10 \\t-> 14.10.2.1.5')", printed_output)  # 5-part is "greater" than 4-part and 3-part
        self.assertIn("call('- 14.10.2 \\t-> 14.10.2.1.5')", printed_output)  # 5-part is "greater" than 4-part
        self.assertIn("call('- 14.10.2.1 \\t-> 14.10.2.1.5')", printed_output)  # 5-part is the only one at this level

        # Verify that in dry-run, no actual copies are made
        self.assertEqual(mock_exec_retry.call_count, 0)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_inverse_order_simple_versions(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test inverse order with simple 3-part versions"""

        # Set up args
        run.args.dry_run = True
        run.args.inverse_specificity_order = True

        # Mock tag lists with standard 3-part versions
        src_tags = ['14.10.2', '14.10.3', '14.11.1', '13.14.0']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Expected tags - same as normal order since all versions have same number of parts
        self.assertIn("call('- 14 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 14.11 \\t-> 14.11.1')", printed_output)
        self.assertIn("call('- 14.10 \\t-> 14.10.3')", printed_output)
        self.assertIn("call('- 13 \\t-> 13.14.0')", printed_output)
        self.assertIn("call('- 13.14 \\t-> 13.14.0')", printed_output)

        # Verify that in dry-run, no actual copies are made
        self.assertEqual(mock_exec_retry.call_count, 0)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_inverse_order_4part_versions(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test inverse order with 4-part versions"""

        # Set up args
        run.args.dry_run = True
        run.args.inverse_specificity_order = True

        # Mock tag lists with 4-part versions
        src_tags = ['7.14.10.2', '7.14.10.3', '7.14.11.1', '7.13.14.0']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Expected tags - same as normal since all have same parts
        self.assertIn("call('- 7 \\t-> 7.14.11.1')", printed_output)
        self.assertIn("call('- 7.14 \\t-> 7.14.11.1')", printed_output)
        self.assertIn("call('- 7.14.11 \\t-> 7.14.11.1')", printed_output)
        self.assertIn("call('- 7.14.10 \\t-> 7.14.10.3')", printed_output)
        self.assertIn("call('- 7.13 \\t-> 7.13.14.0')", printed_output)
        self.assertIn("call('- 7.13.14 \\t-> 7.13.14.0')", printed_output)

        # Verify that in dry-run, no actual copies are made
        self.assertEqual(mock_exec_retry.call_count, 0)

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_inverse_order_three_four_five_parts(self, mock_print, mock_exec_retry, mock_exec_json):
        """Test inverse order with 3, 4, and 5-part versions at same base"""

        # Set up args
        run.args.dry_run = True
        run.args.inverse_specificity_order = True

        # Mock tags with 3, 4, and 5-part versions with same base
        src_tags = ['1.2.3', '1.2.3.4', '1.2.3.4.5', '2.0.0', '2.0.0.1']
        dest_tags = []

        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': src_tags}
                else:
                    return {'Tags': dest_tags}
            elif 'inspect' in cmd:
                return {'Digest': 'sha256:abc123'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output contains expected tag mappings
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Expected tags with inverse order
        # With inverse: more specific versions are "greater"
        self.assertIn("call('- 2 \\t-> 2.0.0.1')", printed_output)  # 4-part is greatest
        self.assertIn("call('- 2.0 \\t-> 2.0.0.1')", printed_output)  # 4-part is greatest
        self.assertIn("call('- 2.0.0 \\t-> 2.0.0.1')", printed_output)  # 4-part is greatest
        self.assertIn("call('- 1 \\t-> 1.2.3.4.5')", printed_output)  # 5-part is greatest
        self.assertIn("call('- 1.2 \\t-> 1.2.3.4.5')", printed_output)  # 5-part is greatest
        self.assertIn("call('- 1.2.3 \\t-> 1.2.3.4.5')", printed_output)  # 5-part is greatest
        self.assertIn("call('- 1.2.3.4 \\t-> 1.2.3.4.5')", printed_output)  # 5-part is the only one at this level

        # Verify that in dry-run, no actual copies are made
        self.assertEqual(mock_exec_retry.call_count, 0)

    def test_inverse_order_version_sorting(self):
        """Test that version sorting respects inverse specificity order"""

        # Set up args
        original_args = run.args
        run.args = MockArgs()
        run.args.inverse_specificity_order = True

        # Parse versions with different specificity
        v3 = run.parse_version('14.10.2')
        v4 = run.parse_version('14.10.2.0')
        v5 = run.parse_version('14.10.2.0.0')

        from functools import cmp_to_key

        versions = [v3, v4, v5]
        sorted_versions = sorted(versions, key=cmp_to_key(run.compare_version))

        # With inverse order: 3-part < 4-part < 5-part (ascending order)
        self.assertEqual(run.str_version(sorted_versions[0]), '14.10.2')
        self.assertEqual(run.str_version(sorted_versions[1]), '14.10.2.0')
        self.assertEqual(run.str_version(sorted_versions[2]), '14.10.2.0.0')

        # The last element (greatest) should be the 5-part version
        sorted_desc = sorted(versions, key=cmp_to_key(run.compare_version), reverse=True)
        self.assertEqual(run.str_version(sorted_desc[0]), '14.10.2.0.0')

        # Clean up
        run.args = original_args

    @patch('run.execAndParseJsonWithRetryRateLimit')
    @patch('run.execWithRetry')
    @patch('builtins.print')
    def test_tag_cleanup_with_timestamp_and_sha(self, mock_print, mock_exec_with_retry, mock_exec_json):
        """Test tag cleanup with timestamp and SHA patterns"""

        # Set up args for the initial scenario
        run.args.prefix = 'test-v'
        run.args.filter = '-SHA-'  # Only process tags with SHA
        run.args.tag_cleanup_patterns = ['-\\d{4}-\\d{2}-\\d{2}T\\d{2}-\\d{2}-\\d{2}-UTC-SHA-[a-f0-9]+']
        run.args.dry_run = False
        run.args.no_copy = False

        # Source tags from the initial scenario
        mock_src_tags = [
            'test-v3',
            'test-v3.13',
            'test-v3.13.13',
            'test-v3.13.13-2024-08-01T13-03-49-UTC-SHA-ea46288f',
            'test-v3.13.13.1',
            'test-v3.13.13.1-2024-08-26T15-06-04-UTC-SHA-3a5f4ddc',
            'test-v3.13.14',
            'test-v3.13.14-2024-08-26T15-06-04-UTC-SHA-3a5f4ddc',
            'test-v3.14',
            'test-v3.14.0',
            'test-v3.14.0-2025-03-13T10-29-34-UTC-SHA-e1e8835c',
        ]

        mock_dest_tags = []

        # Mock skopeo responses: list-tags and inspect
        def mock_skopeo_calls(cmd):
            if 'list-tags' in cmd:
                if 'source' in cmd:
                    return {'Tags': mock_src_tags}
                else:
                    return {'Tags': mock_dest_tags}
            elif 'inspect' in cmd:
                # Mock digest responses for image comparison
                # Different digests for source and dest to force copying
                if 'dest' in cmd:
                    # Dest always returns a different digest to trigger copy
                    return {'Digest': 'sha256:dest-digest'}
                else:
                    # Source digests vary by tag
                    if '2024-08-01' in cmd:
                        return {'Digest': 'sha256:digest1'}
                    elif '2024-08-26' in cmd:
                        return {'Digest': 'sha256:digest2'}
                    elif '2025-03-13' in cmd:
                        return {'Digest': 'sha256:digest3'}
                    return {'Digest': 'sha256:src-digest'}
            return {}

        mock_exec_json.side_effect = mock_skopeo_calls

        # Call the actual implementation
        run.run_main_logic()

        # Verify skopeo was called
        self.assertGreaterEqual(mock_exec_json.call_count, 2)

        # Verify the output shows calculated tags
        print_calls = [str(call) for call in mock_print.call_args_list]
        printed_output = ' '.join(print_calls)

        # Should show the calculated tag mappings
        # Note: The cleanup patterns remove timestamps/SHA from calculated tag names,
        # but original tags (with timestamps) are shown in output and used when copying
        self.assertIn("call('- test-v3 \\t-> test-v3.14.0-2025-03-13T10-29-34-UTC-SHA-e1e8835c')", printed_output)
        self.assertIn("call('- test-v3.14 \\t-> test-v3.14.0-2025-03-13T10-29-34-UTC-SHA-e1e8835c')", printed_output)
        self.assertIn("call('- test-v3.13 \\t-> test-v3.13.14-2024-08-26T15-06-04-UTC-SHA-3a5f4ddc')", printed_output)

        # Verify that execWithRetry was called for copying images
        exec_calls = [str(call) for call in mock_exec_with_retry.call_args_list]

        # Should copy original tags (with timestamps/SHA)
        has_original_tag_copy = any('2024-08-01T13-03-49-UTC-SHA-ea46288f' in call for call in exec_calls)
        self.assertTrue(has_original_tag_copy, 'Should copy original tags with timestamps')

        # Should also create calculated tag aliases (cleaned versions)
        has_calculated_tag = any('test-v3.13' in call and 'test-v3.13.14' in call for call in exec_calls)
        self.assertTrue(has_calculated_tag, 'Should create calculated tag mappings')


if __name__ == '__main__':
    unittest.main()
