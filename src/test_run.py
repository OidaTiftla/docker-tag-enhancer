#!/usr/bin/env python3

import unittest

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
        self.inverse_specificity_order = False
        self.verbose = 0


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
        self.assertEqual(result['parts'], ['14', '10', '2'])
        self.assertIsNone(result['rc'])
        self.assertIsNone(result['ce'])

    def test_parse_major_minor_only(self):
        """Test parsing major.minor versions without patch"""
        result = run.parse_version('14.10')
        self.assertEqual(result['parts'], ['14', '10'])

    def test_parse_major_only(self):
        """Test parsing major version only"""
        result = run.parse_version('13')
        self.assertEqual(result['parts'], ['13'])

    def test_parse_rc_version(self):
        """Test parsing RC (release candidate) versions"""
        result = run.parse_version('14.11.1-rc1')
        self.assertEqual(result['parts'], ['14', '11', '1'])
        self.assertEqual(result['rc'], '1')

    def test_parse_ce_version(self):
        """Test parsing CE (community edition) versions"""
        result = run.parse_version('14.10.2-ce.5')
        self.assertEqual(result['parts'], ['14', '10', '2'])
        self.assertEqual(result['ce'], '5')

    def test_parse_rc_ce_version(self):
        """Test parsing combined RC and CE versions"""
        result = run.parse_version('14.10.2-rc3.ce.5')
        self.assertEqual(result['parts'], ['14', '10', '2'])
        self.assertEqual(result['rc'], '3')
        self.assertEqual(result['ce'], '5')

    def test_parse_with_rest_suffix(self):
        """Test parsing versions with additional suffixes"""
        result = run.parse_version('13.14.0-alpine')
        self.assertEqual(result['parts'], ['13', '14', '0'])
        self.assertEqual(result['rest'], '-alpine')

    def test_parse_invalid_version(self):
        """Test that invalid versions return None"""
        self.assertIsNone(run.parse_version('invalid'))
        self.assertIsNone(run.parse_version('v1.2.3'))  # prefix not allowed without args.prefix

    def test_parse_four_part_version(self):
        """Test parsing 4-part versions (major.minor.patch.build)"""
        result = run.parse_version('1.2.3.4')
        self.assertIsNotNone(result)
        self.assertEqual(result['parts'], ['1', '2', '3', '4'])
        self.assertIsNone(result['rc'])
        self.assertIsNone(result['ce'])

    def test_parse_five_part_version(self):
        """Test parsing 5-part versions"""
        result = run.parse_version('1.2.3.4.5')
        self.assertIsNotNone(result)
        self.assertEqual(result['parts'], ['1', '2', '3', '4', '5'])

    def test_parse_four_part_with_rc(self):
        """Test parsing 4-part versions with RC suffix"""
        result = run.parse_version('1.2.3.4-rc1')
        self.assertIsNotNone(result)
        self.assertEqual(result['parts'], ['1', '2', '3', '4'])
        self.assertEqual(result['rc'], '1')

    def test_parse_four_part_with_ce(self):
        """Test parsing 4-part versions with CE suffix"""
        result = run.parse_version('1.2.3.4-ce.5')
        self.assertIsNotNone(result)
        self.assertEqual(result['parts'], ['1', '2', '3', '4'])
        self.assertEqual(result['ce'], '5')

    def test_parse_four_part_with_rest(self):
        """Test parsing 4-part versions with additional suffix"""
        result = run.parse_version('1.2.3.4-alpine')
        self.assertIsNotNone(result)
        self.assertEqual(result['parts'], ['1', '2', '3', '4'])
        self.assertEqual(result['rest'], '-alpine')

    def test_parse_with_prefix(self):
        """Test parsing with prefix filter"""
        run.args.prefix = 'v'
        result = run.parse_version('v14.10.2')
        self.assertEqual(result['parts'], ['14', '10', '2'])

        # Should return None if prefix doesn't match
        self.assertIsNone(run.parse_version('14.10.2'))

    def test_parse_with_suffix(self):
        """Test parsing with suffix filter"""
        run.args.suffix = '-alpine'
        result = run.parse_version('14.10.2-alpine')
        self.assertEqual(result['parts'], ['14', '10', '2'])

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

    def test_compare_four_part_versions(self):
        """Test comparing 4-part versions"""
        v1 = run.parse_version('1.2.3.4')
        v2 = run.parse_version('1.2.3.5')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

        v3 = run.parse_version('1.2.3.4')
        self.assertEqual(run.compare_version(v1, v3), 0)

    def test_compare_four_part_vs_three_part(self):
        """Test comparing 4-part vs 3-part versions"""
        v1 = run.parse_version('1.2.3')
        v2 = run.parse_version('1.2.3.4')
        # 1.2.3 without build should be greater (less specific, like how major without minor works)
        self.assertEqual(run.compare_version(v1, v2), 1)
        self.assertEqual(run.compare_version(v2, v1), -1)

    def test_compare_five_part_versions(self):
        """Test comparing 5-part versions"""
        v1 = run.parse_version('1.2.3.4.5')
        v2 = run.parse_version('1.2.3.4.6')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_different_build_numbers(self):
        """Test comparing versions with different build numbers"""
        v1 = run.parse_version('14.10.2.100')
        v2 = run.parse_version('14.10.2.200')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_different_build2_numbers(self):
        """Test comparing versions with different build2 numbers"""
        v1 = run.parse_version('14.10.2.3.100')
        v2 = run.parse_version('14.10.2.3.200')
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_five_part_vs_four_part(self):
        """Test comparing 5-part vs 4-part versions"""
        v1 = run.parse_version('1.2.3.4')
        v2 = run.parse_version('1.2.3.4.5')
        # Version without build2 should be greater (less specific)
        self.assertEqual(run.compare_version(v1, v2), 1)
        self.assertEqual(run.compare_version(v2, v1), -1)

    def test_compare_mixed_parts_same_base(self):
        """Test comparing versions with same base but different parts"""
        v3 = run.parse_version('14.10.2')
        v4 = run.parse_version('14.10.2.0')
        v5 = run.parse_version('14.10.2.0.0')

        # 3-part > 4-part > 5-part (less specific is "greater")
        self.assertEqual(run.compare_version(v3, v4), 1)
        self.assertEqual(run.compare_version(v4, v5), 1)
        self.assertEqual(run.compare_version(v3, v5), 1)

    def test_compare_four_part_different_patches(self):
        """Test 4-part versions with different patch numbers"""
        v1 = run.parse_version('1.2.3.10')
        v2 = run.parse_version('1.2.4.5')
        # 1.2.4.x should be greater than 1.2.3.x
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_five_part_different_patches(self):
        """Test 5-part versions with different patch numbers"""
        v1 = run.parse_version('1.2.3.5.100')
        v2 = run.parse_version('1.2.4.1.1')
        # 1.2.4.x.x should be greater than 1.2.3.x.x
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_four_part_with_rc_vs_without(self):
        """Test 4-part RC version vs non-RC"""
        v1 = run.parse_version('1.2.3.4-rc1')
        v2 = run.parse_version('1.2.3.4')
        # RC should be less than non-RC
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_five_part_with_rc_vs_without(self):
        """Test 5-part RC version vs non-RC"""
        v1 = run.parse_version('1.2.3.4.5-rc2')
        v2 = run.parse_version('1.2.3.4.5')
        # RC should be less than non-RC
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)


class TestInverseSpecificityOrder(unittest.TestCase):
    """Test version comparison with inverse specificity order"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()
        # Enable inverse specificity order
        run.args.inverse_specificity_order = True

    def tearDown(self):
        run.args = self.original_args

    def test_compare_with_and_without_minor_inverse(self):
        """Test comparing versions with and without minor component (inverse order)"""
        v1 = run.parse_version('14')
        v2 = run.parse_version('14.10')
        # With inverse order: more specific version (14.10) should be greater
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_four_part_vs_three_part_inverse(self):
        """Test comparing 4-part vs 3-part versions (inverse order)"""
        v1 = run.parse_version('1.2.3')
        v2 = run.parse_version('1.2.3.4')
        # With inverse order: 1.2.3.4 (more specific) should be greater
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_five_part_vs_four_part_inverse(self):
        """Test comparing 5-part vs 4-part versions (inverse order)"""
        v1 = run.parse_version('1.2.3.4')
        v2 = run.parse_version('1.2.3.4.5')
        # With inverse order: 1.2.3.4.5 (more specific) should be greater
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_mixed_parts_same_base_inverse(self):
        """Test comparing versions with same base but different parts (inverse order)"""
        v3 = run.parse_version('14.10.2')
        v4 = run.parse_version('14.10.2.0')
        v5 = run.parse_version('14.10.2.0.0')

        # With inverse order: 5-part > 4-part > 3-part (more specific is "greater")
        self.assertEqual(run.compare_version(v3, v4), -1)
        self.assertEqual(run.compare_version(v4, v5), -1)
        self.assertEqual(run.compare_version(v3, v5), -1)

        # Reverse comparisons
        self.assertEqual(run.compare_version(v4, v3), 1)
        self.assertEqual(run.compare_version(v5, v4), 1)
        self.assertEqual(run.compare_version(v5, v3), 1)

    def test_compare_equal_versions_inverse(self):
        """Test comparing equal versions still works with inverse order"""
        v1 = run.parse_version('14.10.2')
        v2 = run.parse_version('14.10.2')
        self.assertEqual(run.compare_version(v1, v2), 0)

    def test_compare_different_major_inverse(self):
        """Test comparing different major versions (should work same as default)"""
        v1 = run.parse_version('13.0.0')
        v2 = run.parse_version('14.0.0')
        # Major version comparison should work the same regardless of inverse flag
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_different_minor_inverse(self):
        """Test comparing different minor versions (should work same as default)"""
        v1 = run.parse_version('14.9.0')
        v2 = run.parse_version('14.10.0')
        # Minor version comparison should work the same regardless of inverse flag
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_different_patch_inverse(self):
        """Test comparing different patch versions (should work same as default)"""
        v1 = run.parse_version('14.10.1')
        v2 = run.parse_version('14.10.2')
        # Patch version comparison should work the same regardless of inverse flag
        self.assertEqual(run.compare_version(v1, v2), -1)
        self.assertEqual(run.compare_version(v2, v1), 1)

    def test_compare_rc_versions_inverse(self):
        """Test comparing RC versions (should work same as default)"""
        v1 = run.parse_version('14.10.0-rc1')
        v2 = run.parse_version('14.10.0-rc2')
        # RC comparison should work the same regardless of inverse flag
        self.assertEqual(run.compare_version(v1, v2), -1)

        # RC should be less than non-RC
        v3 = run.parse_version('14.10.0')
        self.assertEqual(run.compare_version(v1, v3), -1)
        self.assertEqual(run.compare_version(v3, v1), 1)

    def test_compare_three_vs_four_vs_five_parts_inverse(self):
        """Test comparing 3, 4, and 5-part versions (inverse order)"""
        v3 = run.parse_version('1.2.3')
        v4 = run.parse_version('1.2.3.4')
        v5 = run.parse_version('1.2.3.4.5')

        # With inverse order: 5-part > 4-part > 3-part
        self.assertEqual(run.compare_version(v3, v4), -1)
        self.assertEqual(run.compare_version(v4, v5), -1)
        self.assertEqual(run.compare_version(v3, v5), -1)

        # Ensure consistency in reverse
        self.assertEqual(run.compare_version(v5, v4), 1)
        self.assertEqual(run.compare_version(v4, v3), 1)
        self.assertEqual(run.compare_version(v5, v3), 1)


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

    def test_str_version_four_part(self):
        """Test reconstructing 4-part version"""
        v = run.parse_version('1.2.3.4')
        self.assertEqual(run.str_version(v), '1.2.3.4')

    def test_str_version_five_part(self):
        """Test reconstructing 5-part version"""
        v = run.parse_version('1.2.3.4.5')
        self.assertEqual(run.str_version(v), '1.2.3.4.5')

    def test_str_version_four_part_with_rc(self):
        """Test reconstructing 4-part version with RC"""
        v = run.parse_version('1.2.3.4-rc1')
        self.assertEqual(run.str_version(v), '1.2.3.4-rc1')

    def test_str_version_four_part_with_ce(self):
        """Test reconstructing 4-part version with CE"""
        v = run.parse_version('1.2.3.4-ce.5')
        self.assertEqual(run.str_version(v), '1.2.3.4-ce.5')

    def test_str_version_four_part_with_rc_ce(self):
        """Test reconstructing 4-part version with RC and CE"""
        v = run.parse_version('1.2.3.4-rc2.ce.3')
        self.assertEqual(run.str_version(v), '1.2.3.4-rc2.ce.3')

    def test_str_version_four_part_with_rest(self):
        """Test reconstructing 4-part version with rest suffix"""
        v = run.parse_version('1.2.3.4-alpine')
        self.assertEqual(run.str_version(v), '1.2.3.4-alpine')

    def test_str_version_five_part_with_rc(self):
        """Test reconstructing 5-part version with RC"""
        v = run.parse_version('1.2.3.4.5-rc1')
        self.assertEqual(run.str_version(v), '1.2.3.4.5-rc1')

    def test_str_version_five_part_with_ce(self):
        """Test reconstructing 5-part version with CE"""
        v = run.parse_version('1.2.3.4.5-ce.2')
        self.assertEqual(run.str_version(v), '1.2.3.4.5-ce.2')

    def test_str_version_five_part_with_rest(self):
        """Test reconstructing 5-part version with rest suffix"""
        v = run.parse_version('1.2.3.4.5-debian')
        self.assertEqual(run.str_version(v), '1.2.3.4.5-debian')


class TestMaxVersion(unittest.TestCase):
    """Test finding maximum version from a list"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_max_version_simple_3parts(self):
        """Test finding max from simple versions"""
        versions = [
            run.parse_version('14.10.1'),
            run.parse_version('14.10.2'),
            run.parse_version('14.10.3'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '14.10.3')

    def test_max_version_with_rc_3parts(self):
        """Test that non-RC is greater than RC"""
        versions = [
            run.parse_version('14.10.0-rc1'),
            run.parse_version('14.10.0-rc2'),
            run.parse_version('14.10.0'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '14.10.0')

    def test_max_version_mixed_3parts(self):
        """Test finding max from mixed version types"""
        versions = [
            run.parse_version('13.14.0'),
            run.parse_version('14.10.2'),
            run.parse_version('14.10.3'),
            run.parse_version('14.11.1-rc1'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '14.11.1-rc1')

    def test_max_version_simple_4parts(self):
        """Test finding max from simple versions"""
        versions = [
            run.parse_version('7.14.10.1'),
            run.parse_version('7.14.10.2'),
            run.parse_version('7.14.10.3'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '7.14.10.3')

    def test_max_version_with_rc_4parts(self):
        """Test that non-RC is greater than RC"""
        versions = [
            run.parse_version('7.14.10.0-rc1'),
            run.parse_version('7.14.10.0-rc2'),
            run.parse_version('7.14.10.0'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '7.14.10.0')

    def test_max_version_mixed_4parts(self):
        """Test finding max from mixed version types"""
        versions = [
            run.parse_version('7.13.14.0'),
            run.parse_version('7.14.10.2'),
            run.parse_version('7.14.10.3'),
            run.parse_version('7.14.11.1-rc1'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '7.14.11.1-rc1')

    def test_max_version_simple_5parts(self):
        """Test finding max from simple versions"""
        versions = [
            run.parse_version('2.7.14.10.1'),
            run.parse_version('2.7.14.10.2'),
            run.parse_version('2.7.14.10.3'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '2.7.14.10.3')

    def test_max_version_with_rc_5parts(self):
        """Test that non-RC is greater than RC"""
        versions = [
            run.parse_version('2.7.14.10.0-rc1'),
            run.parse_version('2.7.14.10.0-rc2'),
            run.parse_version('2.7.14.10.0'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '2.7.14.10.0')

    def test_max_version_mixed_5parts(self):
        """Test finding max from mixed version types"""
        versions = [
            run.parse_version('2.7.13.14.0'),
            run.parse_version('2.7.14.10.2'),
            run.parse_version('2.7.14.10.3'),
            run.parse_version('2.7.14.11.1-rc1'),
        ]
        max_v = run.max_version(versions)
        self.assertEqual(run.str_version(max_v), '2.7.14.11.1-rc1')


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


class TestVersionGrouping(unittest.TestCase):
    """Test version grouping logic"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_group_versions_3part_simple(self):
        """Test grouping 3-part versions by major and major.minor"""
        src_tags_str = ['14.10.2', '14.10.3', '14.11.1', '13.14.0']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            '14': ['14.10.2', '14.10.3', '14.11.1'],
            '13': ['13.14.0'],
            '14.10': ['14.10.2', '14.10.3'],
            '14.11': ['14.11.1'],
            '13.14': ['13.14.0'],
            '14.10.2': ['14.10.2'],
            '14.10.3': ['14.10.3'],
            '14.11.1': ['14.11.1'],
            '13.14.0': ['13.14.0'],
        }

        self.assertEqual(grouped_strings, expected)

    def test_group_versions_with_rc(self):
        """Test grouping versions with RC suffixes"""
        src_tags_str = ['14.10.0', '14.10.1-rc1', '14.10.1-rc2', '14.10.1']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            '14': ['14.10.0', '14.10.1-rc1', '14.10.1-rc2', '14.10.1'],
            '14.10': ['14.10.0', '14.10.1-rc1', '14.10.1-rc2', '14.10.1'],
            '14.10.0': ['14.10.0'],
            '14.10.1': ['14.10.1-rc1', '14.10.1-rc2', '14.10.1'],
        }

        self.assertEqual(grouped_strings, expected)

    def test_group_versions_with_rest_suffix(self):
        """Test grouping with rest suffixes"""
        src_tags_str = ['13-alpine', '13-rc1-alpine', '13-rc2-alpine']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            '13-alpine': ['13-alpine', '13-rc1-alpine', '13-rc2-alpine'],
        }

        self.assertEqual(grouped_strings, expected)

    def test_group_versions_4part(self):
        """Test grouping 4-part version tags"""
        src_tags_str = ['7.14.10.2', '7.14.10.3', '7.14.11.1', '7.13.14.0']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            '7': ['7.14.10.2', '7.14.10.3', '7.14.11.1', '7.13.14.0'],
            '7.14': ['7.14.10.2', '7.14.10.3', '7.14.11.1'],
            '7.13': ['7.13.14.0'],
            '7.14.10': ['7.14.10.2', '7.14.10.3'],
            '7.14.11': ['7.14.11.1'],
            '7.13.14': ['7.13.14.0'],
            '7.14.10.2': ['7.14.10.2'],
            '7.14.10.3': ['7.14.10.3'],
            '7.14.11.1': ['7.14.11.1'],
            '7.13.14.0': ['7.13.14.0'],
        }

        self.assertEqual(grouped_strings, expected)

    def test_group_versions_5part(self):
        """Test grouping 5-part version tags"""
        src_tags_str = ['2.7.14.10.2', '2.7.14.10.3', '2.7.14.11.1', '2.7.13.14.0']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            '2': ['2.7.14.10.2', '2.7.14.10.3', '2.7.14.11.1', '2.7.13.14.0'],
            '2.7': ['2.7.14.10.2', '2.7.14.10.3', '2.7.14.11.1', '2.7.13.14.0'],
            '2.7.14': ['2.7.14.10.2', '2.7.14.10.3', '2.7.14.11.1'],
            '2.7.13': ['2.7.13.14.0'],
            '2.7.14.10': ['2.7.14.10.2', '2.7.14.10.3'],
            '2.7.14.11': ['2.7.14.11.1'],
            '2.7.13.14': ['2.7.13.14.0'],
            '2.7.14.10.2': ['2.7.14.10.2'],
            '2.7.14.10.3': ['2.7.14.10.3'],
            '2.7.14.11.1': ['2.7.14.11.1'],
            '2.7.13.14.0': ['2.7.13.14.0'],
        }

        self.assertEqual(grouped_strings, expected)

    def test_group_versions_mixed_parts(self):
        """Test grouping tags with different part counts (3, 4, 5)"""
        src_tags_str = ['14.10.2', '14.10.2.1', '14.10.2.1.5', '14.11.1']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            '14': ['14.10.2', '14.10.2.1', '14.10.2.1.5', '14.11.1'],
            '14.10': ['14.10.2', '14.10.2.1', '14.10.2.1.5'],
            '14.11': ['14.11.1'],
            '14.10.2': ['14.10.2', '14.10.2.1', '14.10.2.1.5'],
            '14.11.1': ['14.11.1'],
            '14.10.2.1': ['14.10.2.1', '14.10.2.1.5'],
            '14.10.2.1.5': ['14.10.2.1.5'],
        }

        self.assertEqual(grouped_strings, expected)

    def test_group_versions_with_prefix_suffix(self):
        """Test grouping with prefix and suffix"""
        # Set up prefix and suffix in args for parsing
        run.args.prefix = 'v'
        run.args.suffix = '-alpine'

        src_tags_str = ['v14.10.2-alpine', 'v14.10.3-alpine', 'v14.11.1-alpine']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags, prefix='v', suffix='-alpine')

        # Convert grouped values to version strings for easier comparison
        grouped_strings = {k: [run.str_version(v) for v in versions] for k, versions in grouped.items()}

        expected = {
            'v14-alpine': ['v14.10.2-alpine', 'v14.10.3-alpine', 'v14.11.1-alpine'],
            'v14.10-alpine': ['v14.10.2-alpine', 'v14.10.3-alpine'],
            'v14.11-alpine': ['v14.11.1-alpine'],
            'v14.10.2-alpine': ['v14.10.2-alpine'],
            'v14.10.3-alpine': ['v14.10.3-alpine'],
            'v14.11.1-alpine': ['v14.11.1-alpine'],
        }

        self.assertEqual(grouped_strings, expected)


class TestCalculateLatestTags(unittest.TestCase):
    """Test the calculate_latest_tags function"""

    def setUp(self):
        self.original_args = run.args
        run.args = MockArgs()

    def tearDown(self):
        run.args = self.original_args

    def test_calculate_latest_tags_3part(self):
        """Test calculating latest tags for 3-part versions"""
        src_tags_str = ['14.10.2', '14.10.3', '14.11.1', '13.14.0']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)
        latest = run.calculate_latest_tags(grouped)

        expected = {
            '14': '14.11.1',
            '13': '13.14.0',
            '14.10': '14.10.3',
            '14.11': '14.11.1',
            '13.14': '13.14.0',
        }

        self.assertEqual(latest, expected)

    def test_calculate_latest_tags_4part(self):
        """Test calculating latest tags for 4-part versions"""
        src_tags_str = ['7.14.10.2', '7.14.10.3', '7.14.11.1']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)
        latest = run.calculate_latest_tags(grouped)

        expected = {
            '7': '7.14.11.1',
            '7.14': '7.14.11.1',
            '7.14.10': '7.14.10.3',
            '7.14.11': '7.14.11.1',
        }

        self.assertEqual(latest, expected)

    def test_calculate_latest_tags_5part(self):
        """Test calculating latest tags for 5-part versions"""
        src_tags_str = ['2.7.14.10.2', '2.7.14.10.3', '2.7.14.11.1']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)
        latest = run.calculate_latest_tags(grouped)

        expected = {
            '2': '2.7.14.11.1',
            '2.7': '2.7.14.11.1',
            '2.7.14': '2.7.14.11.1',
            '2.7.14.10': '2.7.14.10.3',
            '2.7.14.11': '2.7.14.11.1',
        }

        self.assertEqual(latest, expected)

    def test_calculate_latest_tags_with_rc(self):
        """Test calculating latest tags with RC versions"""
        src_tags_str = ['14.10.0', '14.10.1-rc1', '14.10.1-rc2', '14.10.1']
        src_tags = [run.parse_version(t) for t in src_tags_str]

        grouped = run.group_versions(src_tags)
        latest = run.calculate_latest_tags(grouped)

        # Non-RC version should be selected as latest
        expected = {
            '14': '14.10.1',
            '14.10': '14.10.1',
        }

        self.assertEqual(latest, expected)


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

        # Parse and filter
        src_tags = [run.parse_version(t) for t in src_tags_raw]
        src_tags = [t for t in src_tags if t]  # Filter None values

        # Group tags and calculate latest
        src_tags_grouped = run.group_versions(src_tags, prefix=run.args.prefix or '', suffix=run.args.suffix or '')
        src_tags_latest = run.calculate_latest_tags(src_tags_grouped)

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

        # Group tags and calculate latest
        src_tags_grouped = run.group_versions(src_tags)
        src_tags_latest = run.calculate_latest_tags(src_tags_grouped)

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

    def test_complete_tag_calculation_4part(self):
        """Test complete tag calculation with 4-part versions"""
        # Simulate source tags from a registry with 4-part versions
        src_tags_raw = [
            '7.14.10.2', '7.14.10.3', '7.14.10.1',
            '7.14.11.1-rc1', '7.14.11.1',
            '7.13.14.0', '7.13.13.5',
            'invalid-tag',
        ]

        # Parse and filter
        src_tags = [run.parse_version(t) for t in src_tags_raw]
        src_tags = [t for t in src_tags if t]

        # Group tags and calculate latest
        src_tags_grouped = run.group_versions(src_tags, prefix=run.args.prefix or '', suffix=run.args.suffix or '')
        src_tags_latest = run.calculate_latest_tags(src_tags_grouped)

        # Verify expected tag mappings
        expected = {
            '7': '7.14.11.1',
            '7.14': '7.14.11.1',
            '7.13': '7.13.14.0',
            '7.14.10': '7.14.10.3',
            '7.14.11': '7.14.11.1',
            '7.13.13': '7.13.13.5',
            '7.13.14': '7.13.14.0',
        }

        self.assertEqual(src_tags_latest, expected)

    def test_complete_tag_calculation_5part(self):
        """Test complete tag calculation with 5-part versions"""
        # Simulate source tags from a registry with 5-part versions
        src_tags_raw = [
            '2.7.14.10.2', '2.7.14.10.3', '2.7.14.10.1',
            '2.7.14.11.1-rc1', '2.7.14.11.1',
            '2.7.13.14.0', '2.7.13.13.5',
            'invalid-tag',
        ]

        # Parse and filter
        src_tags = [run.parse_version(t) for t in src_tags_raw]
        src_tags = [t for t in src_tags if t]

        # Group tags and calculate latest
        src_tags_grouped = run.group_versions(src_tags, prefix=run.args.prefix or '', suffix=run.args.suffix or '')
        src_tags_latest = run.calculate_latest_tags(src_tags_grouped)

        # Verify expected tag mappings
        expected = {
            '2': '2.7.14.11.1',
            '2.7': '2.7.14.11.1',
            '2.7.14': '2.7.14.11.1',
            '2.7.13': '2.7.13.14.0',
            '2.7.14.10': '2.7.14.10.3',
            '2.7.14.11': '2.7.14.11.1',
            '2.7.13.13': '2.7.13.13.5',
            '2.7.13.14': '2.7.13.14.0',
        }

        self.assertEqual(src_tags_latest, expected)

    def test_complete_tag_calculation_mixed_parts(self):
        """Test complete tag calculation with mixed 3, 4, and 5 part versions"""
        src_tags_raw = [
            '14.10.2',           # 3-part
            '14.10.2.1',         # 4-part (same patch, different build)
            '14.10.2.1.5',       # 5-part (same patch+build, different build2)
            '14.11.1',           # 3-part
            '14.11.2.0',         # 4-part
            '13.14.0.0.1',       # 5-part
        ]

        # Parse and filter
        src_tags = [run.parse_version(t) for t in src_tags_raw]
        src_tags = [t for t in src_tags if t]

        # Group tags and calculate latest
        src_tags_grouped = run.group_versions(src_tags)
        src_tags_latest = run.calculate_latest_tags(src_tags_grouped)

        # Verify: 14.11.2.0 should be max for 14.11 (higher patch)
        # 14.11.2.0 should be max for 14 (highest minor.patch combination)
        # For 14.10 with same patch, 14.10.2 wins (no build > with build, like major.minor logic)
        expected = {
            '14': '14.11.2.0',
            '13': '13.14.0.0.1',
            '14.10': '14.10.2',
            '14.11': '14.11.2.0',
            '13.14': '13.14.0.0.1',
            '13.14.0': '13.14.0.0.1',
            '13.14.0.0': '13.14.0.0.1',
            '14.11.2': '14.11.2.0',
        }

        self.assertEqual(src_tags_latest, expected)


if __name__ == '__main__':
    unittest.main()
