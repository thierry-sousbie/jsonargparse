#!/usr/bin/env python3
"""Unit tests for the jsonargparse module."""

import os
import sys
import stat
import json
import shutil
import tempfile
import pathlib
import unittest
from collections import OrderedDict
from jsonargparse import *
from jsonargparse import _jsonnet


def example_parser():
    """Creates a simple parser for doing tests."""
    parser = ArgumentParser(prog='app', default_meta=False)

    group_one = parser.add_argument_group('Group 1', name='group1')
    group_one.add_argument('--bools.def_false',
        default=False,
        nargs='?',
        action=ActionYesNo)
    group_one.add_argument('--bools.def_true',
        default=True,
        nargs='?',
        action=ActionYesNo)

    group_two = parser.add_argument_group('Group 2', name='group2')
    group_two.add_argument('--lev1.lev2.opt1',
        default='opt1_def')
    group_two.add_argument('--lev1.lev2.opt2',
        default='opt2_def')

    group_three = parser.add_argument_group('Group 3')
    group_three.add_argument('--nums.val1',
        type=int,
        default=1)
    group_three.add_argument('--nums.val2',
        type=float,
        default=2.0)

    return parser


example_yaml = '''
lev1:
  lev2:
    opt1: opt1_yaml
    opt2: opt2_yaml

nums:
  val1: -1
'''

example_env = {
    'APP_LEV1__LEV2__OPT1': 'opt1_env',
    'APP_NUMS__VAL1': '0'
}

example_jsonnet_1 = '''
local make_record(num) = {
    'ref': '#'+(num+1),
    'val': 3*(num/2)+5,
};

{
  'param': 654,
  'records': [make_record(n) for n in std.range(0, 8)],
}
'''

example_jsonnet_2 = '''
local param = std.extVar('param');

local make_record(num) = {
    'ref': '#'+(num+1),
    'val': 3*(num/2)+5,
};

{
  'param': param,
  'records': [make_record(n) for n in std.range(0, 8)],
}
'''


class JsonargparseTests(unittest.TestCase):
    """Tests for jsonargparse."""

    def test_groups(self):
        """Test storage of named groups."""
        parser = example_parser()
        self.assertEqual(['group1', 'group2'], list(sorted(parser.groups.keys())))


    def test_parse_args(self):
        """Test the parse_args method."""
        parser = example_parser()
        self.assertEqual('opt1_arg', parser.parse_args(['--lev1.lev2.opt1', 'opt1_arg']).lev1.lev2.opt1)
        self.assertEqual(9, parser.parse_args(['--nums.val1', '9']).nums.val1)
        self.assertEqual(6.4, parser.parse_args(['--nums.val2', '6.4']).nums.val2)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--nums.val1', '7.5']))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--nums.val2', 'eight']))


    def test_dump(self):
        """Test the dump method."""
        parser = example_parser()
        cfg1 = parser.get_defaults()
        cfg2 = parser.parse_string(parser.dump(cfg1))
        self.assertEqual(cfg1, cfg2)
        delattr(cfg2, 'lev1')
        parser.dump(cfg2)


    def test_usage_and_exit_error_handler(self):
        """Test the usage_and_exit_error_handler error handler."""
        parser = ArgumentParser(prog='app', error_handler='usage_and_exit_error_handler')
        parser.add_argument('--val', type=int)
        self.assertEqual(8, parser.parse_args(['--val', '8']).val)
        sys.stderr.write('\n')
        self.assertRaises(SystemExit, lambda: parser.parse_args(['--val', 'eight']))


    def test_yes_no_action(self):
        """Test the correct functioning of ActionYesNo."""
        parser = example_parser()
        defaults = parser.get_defaults()
        self.assertEqual(False, defaults.bools.def_false)
        self.assertEqual(True,  defaults.bools.def_true)
        self.assertEqual(True,  parser.parse_args(['--bools.def_false']).bools.def_false)
        self.assertEqual(False, parser.parse_args(['--no_bools.def_false']).bools.def_false)
        self.assertEqual(True,  parser.parse_args(['--bools.def_true']).bools.def_true)
        self.assertEqual(False, parser.parse_args(['--no_bools.def_true']).bools.def_true)
        self.assertEqual(True,  parser.parse_args(['--bools.def_false=true']).bools.def_false)
        self.assertEqual(False, parser.parse_args(['--bools.def_false=false']).bools.def_false)
        self.assertEqual(True,  parser.parse_args(['--bools.def_false=yes']).bools.def_false)
        self.assertEqual(False, parser.parse_args(['--bools.def_false=no']).bools.def_false)
        self.assertEqual(True,  parser.parse_args(['--no_bools.def_true=no']).bools.def_true)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--bools.def_true nope']))
        parser = ArgumentParser()
        parser.add_argument('--val', action=ActionYesNo)
        self.assertEqual(True,  parser.parse_args(['--val']).val)
        self.assertEqual(False, parser.parse_args(['--no_val']).val)
        parser = ArgumentParser()
        parser.add_argument('--with-val', action=ActionYesNo(yes_prefix='with-', no_prefix='without-'))
        self.assertEqual(True,  parser.parse_args(['--with-val']).with_val)
        self.assertEqual(False, parser.parse_args(['--without-val']).with_val)
        parser = ArgumentParser()
        self.assertRaises(ValueError, lambda: parser.add_argument('--val', action=ActionYesNo(yes_prefix='yes_')))


    def test_bool_type(self):
        """Test the correct functioning of type=bool."""
        parser = ArgumentParser()
        parser.add_argument('--val', type=bool)
        self.assertEqual(True,  parser.parse_args(['--val', 'true']).val)
        self.assertEqual(True,  parser.parse_args(['--val', 'yes']).val)
        self.assertEqual(False, parser.parse_args(['--val', 'false']).val)
        self.assertEqual(False, parser.parse_args(['--val', 'no']).val)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--val', '1']))
        self.assertRaises(ValueError, lambda: parser.add_argument('--val2', type=bool, nargs='+'))


    def test_nargs(self):
        """Test the correct functioning of nargs."""
        parser = ArgumentParser()
        parser.add_argument('--val', nargs='+', type=int)
        self.assertEqual([9],        parser.parse_args(['--val', '9']).val)
        self.assertEqual([3, 6, 2],  parser.parse_args(['--val', '3', '6', '2']).val)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--val']))
        parser = ArgumentParser()
        parser.add_argument('--val', nargs='*', type=float)
        self.assertEqual([5.2, 1.9], parser.parse_args(['--val', '5.2', '1.9']).val)
        self.assertEqual([],         parser.parse_args(['--val']).val)
        parser = ArgumentParser()
        parser.add_argument('--val', nargs='?', type=str)
        self.assertEqual('~',        parser.parse_args(['--val', '~']).val)
        self.assertEqual(None,       parser.parse_args(['--val']).val)
        parser = ArgumentParser()
        parser.add_argument('--val', nargs=2)
        self.assertEqual(['q', 'p'], parser.parse_args(['--val', 'q', 'p']).val)
        parser = ArgumentParser()
        parser.add_argument('--val', nargs=1)
        self.assertEqual(['-'],      parser.parse_args(['--val', '-']).val)


    def test_parse_yaml(self):
        """Test the parsing and checking of yaml."""
        parser = example_parser()

        cfg1 = parser.parse_string(example_yaml)
        self.assertEqual('opt1_yaml', cfg1.lev1.lev2.opt1)
        self.assertEqual('opt2_yaml', cfg1.lev1.lev2.opt2)
        self.assertEqual(-1,  cfg1.nums.val1)
        self.assertEqual(2.0, cfg1.nums.val2)
        self.assertEqual(False, cfg1.bools.def_false)
        self.assertEqual(True,  cfg1.bools.def_true)

        cfg2 = parser.parse_string(example_yaml, defaults=False)
        self.assertFalse(hasattr(cfg2, 'bools'))
        self.assertTrue(hasattr(cfg2, 'nums'))

        tmpdir = tempfile.mkdtemp(prefix='_jsonargparse_test_')
        yaml_file = os.path.realpath(os.path.join(tmpdir, 'example.yaml'))

        with open(yaml_file, 'w') as output_file:
            output_file.write(example_yaml)
        self.assertEqual(cfg1, parser.parse_path(yaml_file, defaults=True))
        self.assertEqual(cfg2, parser.parse_path(yaml_file, defaults=False))
        self.assertNotEqual(cfg2, parser.parse_path(yaml_file, defaults=True))
        self.assertNotEqual(cfg1, parser.parse_path(yaml_file, defaults=False))
        self.assertTrue(hasattr(parser.parse_path(yaml_file, with_meta=True), '__cwd__'))
        self.assertFalse(hasattr(parser.parse_path(yaml_file), '__cwd__'))

        with open(yaml_file, 'w') as output_file:
            output_file.write(example_yaml+'  val2: eight\n')
        self.assertRaises(ParserError, lambda: parser.parse_path(yaml_file))
        with open(yaml_file, 'w') as output_file:
            output_file.write(example_yaml+'  val3: key_not_defined\n')
        self.assertRaises(ParserError, lambda: parser.parse_path(yaml_file))

        shutil.rmtree(tmpdir)


    def test_parse_env(self):
        """Test the parsing of environment variables."""
        parser = example_parser()
        cfg = parser.parse_env(env=example_env)
        self.assertEqual('opt1_env', cfg.lev1.lev2.opt1)
        self.assertEqual(0, cfg.nums.val1)
        cfg = parser.parse_env(env=example_env, defaults=False)
        self.assertFalse(hasattr(cfg, 'bools'))
        self.assertTrue(hasattr(cfg, 'nums'))
        parser.add_argument('--cfg', action=ActionConfigFile)
        env = OrderedDict(example_env)
        env['APP_CFG'] = '{"nums": {"val1": 1}}'
        self.assertEqual(0, parser.parse_env(env=env).nums.val1)
        parser.add_argument('req', nargs='+')
        env['APP_REQ'] = 'abc'
        self.assertEqual(['abc'], parser.parse_env(env=env).req)
        env['APP_REQ'] = '["abc", "xyz"]'
        self.assertEqual(['abc', 'xyz'], parser.parse_env(env=env).req)


    def test_required(self):
        """Test the user of required arguments."""
        parser = ArgumentParser(env_prefix='APP')
        group = parser.add_argument_group('Group 1')
        group.add_argument('--req1', required=True)
        parser.add_argument('--lev1.req2', required=True)
        cfg = parser.parse_args(['--req1', 'val1', '--lev1.req2', 'val2'])
        self.assertEqual('val1', cfg.req1)
        self.assertEqual('val2', cfg.lev1.req2)
        cfg = parser.parse_string('{"req1":"val3","lev1":{"req2":"val4"}}')
        self.assertEqual('val3', cfg.req1)
        self.assertEqual('val4', cfg.lev1.req2)
        cfg = parser.parse_env(env={'APP_REQ1': 'val5', 'APP_LEV1__REQ2': 'val6'})
        self.assertEqual('val5', cfg.req1)
        self.assertEqual('val6', cfg.lev1.req2)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--req1', 'val1']))
        self.assertRaises(ParserError, lambda: parser.parse_string('{"lev1":{"req2":"val4"}}'))
        self.assertRaises(ParserError, lambda: parser.parse_env(env={}))


    def test_default_config_files(self):
        """Test the use of default_config_files."""
        tmpdir = os.path.realpath(tempfile.mkdtemp(prefix='_jsonargparse_test_'))
        default_config_file = os.path.realpath(os.path.join(tmpdir, 'example.yaml'))
        with open(default_config_file, 'w') as output_file:
            output_file.write('op1: from default config file\n')

        parser = ArgumentParser(prog='app', default_config_files=[default_config_file])
        parser.add_argument('--op1', default='from parser default')
        parser.add_argument('--op2', default='from parser default')

        cfg = parser.get_defaults()
        self.assertEqual('from default config file', cfg.op1)
        self.assertEqual('from parser default', cfg.op2)

        shutil.rmtree(tmpdir)


    def test_precedence(self):
        """Test the parsing precedence for different sources."""
        tmpdir = tempfile.mkdtemp(prefix='_jsonargparse_test_')
        input1_config_file = os.path.realpath(os.path.join(tmpdir, 'input1.yaml'))
        input2_config_file = os.path.realpath(os.path.join(tmpdir, 'input2.yaml'))
        default_config_file = os.path.realpath(os.path.join(tmpdir, 'default.yaml'))

        parser = ArgumentParser(prog='app',
                                default_env=True,
                                default_config_files=[default_config_file])
        parser.add_argument('--op1', default='from parser default')
        parser.add_argument('--op2')
        parser.add_argument('--cfg', action=ActionConfigFile)

        with open(input1_config_file, 'w') as output_file:
            output_file.write('op1: from input config file')
        with open(input2_config_file, 'w') as output_file:
            output_file.write('op2: unused')

        ## check parse_env precedence ##
        self.assertEqual('from parser default', parser.parse_env().op1)
        with open(default_config_file, 'w') as output_file:
            output_file.write('op1: from default config file')
        self.assertEqual('from default config file', parser.parse_env().op1)
        env = {'APP_CFG': '{"op1": "from env config"}'}
        self.assertEqual('from env config', parser.parse_env(env=env).op1)
        env['APP_OP1'] = 'from env var'
        self.assertEqual('from env var', parser.parse_env(env=env).op1)

        ## check parse_path precedence ##
        os.remove(default_config_file)
        for key in [k for k in ['APP_CFG', 'APP_OP1'] if k in os.environ]:
            del os.environ[key]
        self.assertEqual('from parser default', parser.parse_path(input2_config_file).op1)
        with open(default_config_file, 'w') as output_file:
            output_file.write('op1: from default config file')
        self.assertEqual('from default config file', parser.parse_path(input2_config_file).op1)
        os.environ['APP_CFG'] = input1_config_file
        self.assertEqual('from input config file', parser.parse_path(input2_config_file).op1)
        os.environ['APP_OP1'] = 'from env var'
        self.assertEqual('from env var', parser.parse_path(input2_config_file).op1)
        os.environ['APP_CFG'] = input2_config_file
        self.assertEqual('from input config file', parser.parse_path(input1_config_file).op1)

        ## check parse_args precedence ##
        os.remove(default_config_file)
        for key in ['APP_CFG', 'APP_OP1']:
            del os.environ[key]
        self.assertEqual('from parser default', parser.parse_args(args=[]).op1)
        with open(default_config_file, 'w') as output_file:
            output_file.write('op1: from default config file')
        self.assertEqual('from default config file', parser.parse_args(args=[]).op1)
        os.environ['APP_CFG'] = input1_config_file
        self.assertEqual('from input config file', parser.parse_args(args=[]).op1)
        os.environ['APP_OP1'] = 'from env var'
        self.assertEqual('from env var', parser.parse_args(args=[]).op1)
        os.environ['APP_CFG'] = input2_config_file
        self.assertEqual('from arg', parser.parse_args(args=['--op1', 'from arg']).op1)
        self.assertEqual('from arg', parser.parse_args(args=['--cfg', input1_config_file, '--op1', 'from arg']).op1)
        self.assertEqual('from input config file', parser.parse_args(args=['--op1', 'from arg', '--cfg', input1_config_file]).op1)

        for key in ['APP_CFG', 'APP_OP1']:
            del os.environ[key]
        shutil.rmtree(tmpdir)


    def test_strip_unknown(self):
        """Test the strip_unknown function."""
        base_parser = example_parser()
        ext_parser = example_parser()
        ext_parser.add_argument('--val')
        ext_parser.add_argument('--lev1.lev2.opt3', default='opt3_def')
        ext_parser.add_argument('--lev1.opt4', default='opt3_def')
        ext_parser.add_argument('--nums.val3', type=float, default=1.5)
        cfg = ext_parser.parse_args([])
        cfg = base_parser.strip_unknown(cfg)
        base_parser.check_config(cfg, skip_none=False)


    def test_path(self):
        """Test options of the Path class."""
        tmpdir = os.path.realpath(tempfile.mkdtemp(prefix='_jsonargparse_test_'))

        file_rw = os.path.join(tmpdir, 'file_rw')
        file_r = os.path.join(tmpdir, 'file_r')
        file_ = os.path.join(tmpdir, 'file_')
        dir_rwx = os.path.join(tmpdir, 'dir_rwx')
        dir_rx = os.path.join(tmpdir, 'dir_rx')
        dir_x = os.path.join(tmpdir, 'dir_x')
        dir_file_rx = os.path.join(dir_x, 'file_rx')

        pathlib.Path(file_rw).touch()
        pathlib.Path(file_r).touch()
        pathlib.Path(file_).touch()
        os.mkdir(dir_rwx)
        os.mkdir(dir_rx)
        os.mkdir(dir_x)
        pathlib.Path(dir_file_rx).touch()

        os.chmod(file_rw, (stat.S_IREAD | stat.S_IWRITE))
        os.chmod(file_r, stat.S_IREAD)
        os.chmod(file_, 0)
        os.chmod(dir_file_rx, (stat.S_IREAD | stat.S_IEXEC))
        os.chmod(dir_rwx, (stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC))
        os.chmod(dir_rx, (stat.S_IREAD | stat.S_IEXEC))
        os.chmod(dir_x, stat.S_IEXEC)

        Path(file_rw, 'frw')
        Path(file_r, 'fr')
        Path(file_, 'f')
        Path(dir_file_rx, 'fr')
        self.assertRaises(TypeError, lambda: Path(file_rw, 'fx'))
        self.assertRaises(TypeError, lambda: Path(file_r, 'fw'))
        self.assertRaises(TypeError, lambda: Path(file_, 'fr'))
        self.assertRaises(TypeError, lambda: Path(dir_file_rx, 'fw'))
        Path(dir_rwx, 'drwx')
        Path(dir_rx, 'drx')
        Path(dir_x, 'dx')
        self.assertRaises(TypeError, lambda: Path(dir_rx, 'dw'))
        self.assertRaises(TypeError, lambda: Path(dir_x, 'dr'))
        Path(file_rw, 'fcrw')
        Path(os.path.join(tmpdir, 'file_c'), 'fc')
        Path(dir_rwx, 'dcrwx')
        Path(os.path.join(tmpdir, 'dir_c'), 'dc')
        self.assertRaises(TypeError, lambda: Path(os.path.join(dir_rx, 'file_c'), 'fc'))
        self.assertRaises(TypeError, lambda: Path(os.path.join(dir_rx, 'dir_c'), 'dc'))
        self.assertRaises(TypeError, lambda: Path(file_rw, 'dc'))
        self.assertRaises(TypeError, lambda: Path(dir_rwx, 'fc'))
        self.assertRaises(TypeError, lambda: Path(os.path.join(dir_rwx, 'ne', 'file_c'), 'fc'))
        self.assertRaises(TypeError, lambda: Path(file_rw, 'fW'))
        self.assertRaises(TypeError, lambda: Path(file_rw, 'fR'))
        self.assertRaises(TypeError, lambda: Path(dir_rwx, 'dX'))
        self.assertRaises(TypeError, lambda: Path(file_rw, 'F'))
        self.assertRaises(TypeError, lambda: Path(dir_rwx, 'D'))

        os.chmod(dir_x, (stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC))
        shutil.rmtree(tmpdir)


    def test_configfile_filepath(self):
        """Test the use of ActionConfigFile and ActionPath."""
        tmpdir = os.path.realpath(tempfile.mkdtemp(prefix='_jsonargparse_test_'))
        os.mkdir(os.path.join(tmpdir, 'example'))
        rel_yaml_file = os.path.join('..', 'example', 'example.yaml')
        abs_yaml_file = os.path.realpath(os.path.join(tmpdir, 'example', rel_yaml_file))
        with open(abs_yaml_file, 'w') as output_file:
            output_file.write('file: '+rel_yaml_file+'\ndir: '+tmpdir+'\n')

        parser = ArgumentParser(prog='app')
        parser.add_argument('--cfg',
            action=ActionConfigFile)
        parser.add_argument('--file',
            action=ActionPath(mode='fr'))
        parser.add_argument('--dir',
            action=ActionPath(mode='drw'))
        parser.add_argument('--files',
            nargs='+',
            action=ActionPath(mode='fr'))

        cfg = parser.parse_args(['--cfg', abs_yaml_file])
        self.assertEqual(tmpdir, os.path.realpath(cfg.dir(absolute=True)))
        self.assertEqual(abs_yaml_file, os.path.realpath(cfg.cfg[0](absolute=False)))
        self.assertEqual(abs_yaml_file, os.path.realpath(cfg.cfg[0](absolute=True)))
        self.assertEqual(rel_yaml_file, cfg.file(absolute=False))
        self.assertEqual(abs_yaml_file, os.path.realpath(cfg.file(absolute=True)))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--cfg', abs_yaml_file+'~']))

        cfg = parser.parse_args(['--cfg', 'file: '+abs_yaml_file+'\ndir: '+tmpdir+'\n'])
        self.assertEqual(tmpdir, os.path.realpath(cfg.dir(absolute=True)))
        self.assertEqual(None, cfg.cfg[0])
        self.assertEqual(abs_yaml_file, os.path.realpath(cfg.file(absolute=True)))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--cfg', '{"k":"v"}']))

        cfg = parser.parse_args(['--file', abs_yaml_file, '--dir', tmpdir])
        self.assertEqual(tmpdir, os.path.realpath(cfg.dir(absolute=True)))
        self.assertEqual(abs_yaml_file, os.path.realpath(cfg.file(absolute=True)))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--dir', abs_yaml_file]))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--file', tmpdir]))

        cfg = parser.parse_args(['--files', abs_yaml_file, abs_yaml_file])
        self.assertTrue(isinstance(cfg.files, list))
        self.assertEqual(2, len(cfg.files))
        self.assertEqual(abs_yaml_file, os.path.realpath(cfg.files[-1](absolute=True)))

        self.assertRaises(ValueError, lambda: parser.add_argument('--op1', action=ActionPath))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op2', action=ActionPath()))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op3', action=ActionPath(mode='+')))

        shutil.rmtree(tmpdir)


    def test_filepathlist(self):
        """Test the use of ActionPathList."""
        tmpdir = os.path.realpath(tempfile.mkdtemp(prefix='_jsonargparse_test_'))
        pathlib.Path(os.path.join(tmpdir, 'file1')).touch()
        pathlib.Path(os.path.join(tmpdir, 'file2')).touch()
        pathlib.Path(os.path.join(tmpdir, 'file3')).touch()
        pathlib.Path(os.path.join(tmpdir, 'file4')).touch()
        pathlib.Path(os.path.join(tmpdir, 'file5')).touch()
        list_file = os.path.join(tmpdir, 'files.lst')
        list_file2 = os.path.join(tmpdir, 'files2.lst')
        with open(list_file, 'w') as output_file:
            output_file.write('file1\nfile2\nfile3\nfile4\n')
        with open(list_file2, 'w') as output_file:
            output_file.write('file5\n')

        parser = ArgumentParser(prog='app')
        parser.add_argument('--list',
            nargs='+',
            action=ActionPathList(mode='fr', rel='list'))
        parser.add_argument('--list_cwd',
            action=ActionPathList(mode='fr', rel='cwd'))

        cfg = parser.parse_args(['--list', list_file])
        self.assertEqual(4, len(cfg.list))
        self.assertEqual(['file1', 'file2', 'file3', 'file4'], [x(absolute=False) for x in cfg.list])

        cfg = parser.parse_args(['--list', list_file, list_file2])
        self.assertEqual(5, len(cfg.list))
        self.assertEqual(['file1', 'file2', 'file3', 'file4', 'file5'], [x(absolute=False) for x in cfg.list])

        cwd = os.getcwd()
        os.chdir(tmpdir)
        cfg = parser.parse_args(['--list_cwd', list_file])
        self.assertEqual(4, len(cfg.list_cwd))
        self.assertEqual(['file1', 'file2', 'file3', 'file4'], [x(absolute=False) for x in cfg.list_cwd])
        os.chdir(cwd)

        self.assertRaises(ValueError, lambda: parser.add_argument('--op1', action=ActionPathList))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op2', action=ActionPathList(mode='fr'), nargs='*'))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op3', action=ActionPathList(mode='fr', rel='.')))

        shutil.rmtree(tmpdir)


    def test_actionparser(self):
        """Test the use of ActionParser."""
        parser = ArgumentParser(prog='xyz')
        parser.add_argument('--inner.vals',
            action=ActionParser(parser=example_parser()))
        parser.add_argument('--inner.flag',
            default='flag_def')
        parser.add_argument('--cfg',
            action=ActionConfigFile)

        cfg = parser.get_defaults()
        self.assertEqual('opt1_def', parser.get_defaults().inner.vals.lev1.lev2.opt1)

        tmpdir = tempfile.mkdtemp(prefix='_jsonargparse_test_')
        yaml1_file = os.path.join(tmpdir, 'example1.yaml')
        yaml2_file = os.path.join(tmpdir, 'example2.yaml')
        yaml3_file = os.path.join(tmpdir, 'example3.yaml')

        with open(yaml1_file, 'w') as output_file:
            output_file.write('inner:\n  vals: example2.yaml\n  flag: flag_yaml\n')
        with open(yaml2_file, 'w') as output_file:
            output_file.write(example_yaml)
        with open(yaml3_file, 'w') as output_file:
            output_file.write('inner:\n  flag: flag_yaml\n')
        cfg = parser.parse_args(['--cfg', yaml1_file], with_meta=False)
        self.assertEqual('flag_yaml', cfg.inner.flag)
        self.assertEqual('opt1_yaml', cfg.inner.vals.lev1.lev2.opt1)

        cfg = parser.parse_args(['--cfg', yaml3_file], with_meta=False)
        self.assertEqual('flag_yaml', cfg.inner.flag)
        self.assertEqual('opt1_def', cfg.inner.vals.lev1.lev2.opt1)

        with open(yaml3_file, 'w') as output_file:
            output_file.write(parser.dump(cfg))
        self.assertEqual(cfg.inner, parser.parse_path(yaml3_file, with_meta=False).inner)

        #cfg = parser.parse_args(['--cfg', yaml1_file, '--inner.vals.lev1.lev2.opt1', 'opt1_arg'])
        #self.assertEqual('opt1_arg', cfg.inner.vals.lev1.lev2.opt1)

        self.assertEqual('flag_env', parser.parse_env(env={'XYZ_INNER__FLAG': 'flag_env'}).inner.flag)
        self.assertEqual('opt1_env', parser.parse_env(env={'XYZ_INNER__VALS__LEV1__LEV2__OPT1': 'opt1_env'}).inner.vals.lev1.lev2.opt1)

        self.assertRaises(ValueError, lambda: parser.add_argument('--op1', action=ActionParser))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op2', action=ActionParser()))

        shutil.rmtree(tmpdir)


    def test_save(self):
        """Test the use of save."""
        parser = ArgumentParser()
        schema = {
            'type': 'object',
            'properties': {
                'a': {'type': 'number'},
                'b': {'type': 'number'},
            },
        }
        parser.add_argument('--schema',
            default={'a': 1, 'b': 2},
            action=ActionJsonSchema(schema=schema))
        parser.add_argument('--jsonnet',
            default={'c': 3, 'd': 4},
            action=ActionJsonnetExtVars)
        parser.add_argument('--parser',
            action=ActionParser(parser=example_parser()))

        tmpdir = tempfile.mkdtemp(prefix='_jsonargparse_test_')
        indir = os.path.join(tmpdir, 'input')
        outdir = os.path.join(tmpdir, 'output')
        os.mkdir(outdir)
        os.mkdir(indir)
        main_file = os.path.join(indir, 'main.yaml')
        schema_file = os.path.join(indir, 'schema.yaml')
        jsonnet_file = os.path.join(indir, 'jsonnet.yaml')
        parser_file = os.path.join(indir, 'parser.yaml')

        cfg1 = parser.get_defaults()

        with open(main_file, 'w') as output_file:
            output_file.write('parser: parser.yaml\nschema: schema.yaml\njsonnet: jsonnet.yaml\n')
        with open(schema_file, 'w') as output_file:
            output_file.write(json.dumps(namespace_to_dict(cfg1.schema))+'\n')
        with open(jsonnet_file, 'w') as output_file:
            output_file.write(json.dumps(namespace_to_dict(cfg1.jsonnet))+'\n')
        with open(parser_file, 'w') as output_file:
            output_file.write(example_parser().dump(cfg1.parser))

        cfg2 = parser.parse_path(main_file, with_meta=True)
        self.assertEqual(namespace_to_dict(cfg1), parser.strip_meta(cfg2))

        parser.save(cfg2, os.path.join(outdir, 'main.yaml'))
        self.assertTrue(os.path.isfile(os.path.join(outdir, 'schema.yaml')))
        self.assertTrue(os.path.isfile(os.path.join(outdir, 'jsonnet.yaml')))
        self.assertTrue(os.path.isfile(os.path.join(outdir, 'parser.yaml')))

        cfg3 = parser.parse_path(os.path.join(outdir, 'main.yaml'), with_meta=False)
        self.assertEqual(namespace_to_dict(cfg1), namespace_to_dict(cfg3))

        self.assertRaises(ValueError, lambda: parser.save(cfg2, os.path.join(outdir, 'main.yaml')))

        parser.save(cfg2, os.path.join(outdir, 'main.yaml'), multifile=False, overwrite=True)
        cfg4 = parser.parse_path(os.path.join(outdir, 'main.yaml'), with_meta=False)
        self.assertEqual(namespace_to_dict(cfg1), namespace_to_dict(cfg4))

        shutil.rmtree(tmpdir)


    @unittest.skipIf(isinstance(jsonvalidator, Exception), 'jsonschema package is required :: '+str(jsonvalidator))
    def test_jsonschema(self):
        """Test the use of ActionJsonSchema."""

        schema1 = {
            'type': 'array',
            'items': {'type': 'integer'},
        }

        schema2 = {
            'type': 'object',
            'properties': {
                'k1': {'type': 'string'},
                'k2': {'type': 'integer'},
                'k3': {
                    'type': 'number',
                    'default': 17,
                },
            },
            'additionalProperties': False,
        }

        schema3 = {
            'type': 'object',
            'properties': {
                'n1': {
                    'type': 'array',
                    'minItems': 1,
                    'items': {
                        'type': 'object',
                        'properties': {
                            'k1': {'type': 'string'},
                            'k2': {'type': 'integer'},
                        },
                    },
                },
            },
        }

        parser = ArgumentParser(prog='app', default_meta=False)
        parser.add_argument('--op1',
            action=ActionJsonSchema(schema=schema1))
        parser.add_argument('--op2',
            action=ActionJsonSchema(schema=schema2))
        parser.add_argument('--op3',
            action=ActionJsonSchema(schema=schema3))
        parser.add_argument('--cfg',
            action=ActionConfigFile)

        op1_val = [1, 2, 3, 4]
        op2_val = {'k1': 'one', 'k2': 2, 'k3': 3.3}

        self.assertEqual(op1_val, parser.parse_args(['--op1', str(op1_val)]).op1)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--op1', '[1, "two"]']))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--op1', '[1.5, 2]']))

        self.assertEqual(op2_val, vars(parser.parse_args(['--op2', str(op2_val)]).op2))
        self.assertEqual(17, parser.parse_args(['--op2', '{"k2": 2}']).op2.k3)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--op2', '{"k1": 1}']))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--op2', '{"k2": "2"}']))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--op2', '{"k4": 4}']))

        tmpdir = os.path.realpath(tempfile.mkdtemp(prefix='_jsonargparse_test_'))
        op1_file = os.path.join(tmpdir, 'op1.json')
        op2_file = os.path.join(tmpdir, 'op2.json')
        cfg1_file = os.path.join(tmpdir, 'cfg1.yaml')
        cfg3_file = os.path.join(tmpdir, 'cfg3.yaml')
        cfg2_str = 'op1:\n  '+str(op1_val)+'\nop2:\n  '+str(op2_val)+'\n'
        with open(op1_file, 'w') as f:
            f.write(str(op1_val))
        with open(op2_file, 'w') as f:
            f.write(str(op2_val))
        with open(cfg1_file, 'w') as f:
            f.write('op1:\n  '+op1_file+'\nop2:\n  '+op2_file+'\n')
        with open(cfg3_file, 'w') as f:
            f.write('op3:\n  n1:\n  - '+str(op2_val)+'\n')

        cfg = namespace_to_dict(parser.parse_path(cfg1_file))
        self.assertEqual(op1_val, cfg['op1'])
        self.assertEqual(op2_val, cfg['op2'])

        cfg = namespace_to_dict(parser.parse_string(cfg2_str))
        self.assertEqual(op1_val, cfg['op1'])
        self.assertEqual(op2_val, cfg['op2'])

        cfg = parser.parse_args(['--cfg', cfg3_file])
        self.assertEqual(op2_val, namespace_to_dict(cfg.op3.n1[0]))
        parser.check_config(cfg, skip_none=True)

        shutil.rmtree(tmpdir)


    @unittest.skipIf(isinstance(_jsonnet, Exception), 'jsonnet package is required :: '+str(_jsonnet))
    def test_mode_jsonnet(self):
        """Test the use of parser_mode='jsonnet'."""

        schema = {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'ref': {'type': 'string'},
                    'val': {'type': 'number'},
                },
            },
        }

        parser = ArgumentParser(parser_mode='jsonnet')
        parser.add_argument('--cfg',
            action=ActionConfigFile)
        parser.add_argument('--param',
            type=int)
        parser.add_argument('--records',
            action=ActionJsonSchema(schema=schema))

        tmpdir = tempfile.mkdtemp(prefix='_jsonargparse_test_')
        jsonnet_file = os.path.join(tmpdir, 'example.jsonnet')
        with open(jsonnet_file, 'w') as output_file:
            output_file.write(example_jsonnet_1)

        cfg = parser.parse_args(['--cfg', jsonnet_file])
        self.assertEqual(654, cfg.param)
        self.assertEqual(9, len(cfg.records))
        self.assertEqual('#8', cfg.records[-2].ref)
        self.assertEqual(15.5, cfg.records[-2].val)

        shutil.rmtree(tmpdir)


    @unittest.skipIf(isinstance(_jsonnet, Exception), 'jsonnet package is required :: '+str(_jsonnet))
    @unittest.skipIf(isinstance(jsonvalidator, Exception), 'jsonschema package is required :: '+str(jsonvalidator))
    def test_action_jsonnet(self):
        """Test the use of ActionJsonnet."""
        parser = ArgumentParser()
        parser.add_argument('--input.ext_vars',
            action=ActionJsonnetExtVars)
        parser.add_argument('--input.jsonnet',
            action=ActionJsonnet(ext_vars='input.ext_vars'))

        cfg = parser.parse_args(['--input.ext_vars', '{"param": 123}', '--input.jsonnet', example_jsonnet_2])
        self.assertEqual(123, cfg.input.jsonnet.param)
        self.assertEqual(9, len(cfg.input.jsonnet.records))
        self.assertEqual('#8', cfg.input.jsonnet.records[-2].ref)
        self.assertEqual(15.5, cfg.input.jsonnet.records[-2].val)

        self.assertRaises(ParserError, lambda: parser.parse_args(['--input.jsonnet', example_jsonnet_2]))


    def test_operators(self):
        """Test the use of ActionOperators."""
        parser = ArgumentParser(prog='app')
        parser.add_argument('--le0',
            action=ActionOperators(expr=('<', 0)))
        parser.add_argument('--gt1.a.le4',
            action=ActionOperators(expr=[('>', 1.0), ('<=', 4.0)], join='and', type=float))
        parser.add_argument('--lt5.o.ge10.o.eq7',
            action=ActionOperators(expr=[('<', 5), ('>=', 10), ('==', 7)], join='or', type=int))
        def int_or_off(x): return x if x == 'off' else int(x)
        parser.add_argument('--gt0.o.off',
            action=ActionOperators(expr=[('>', 0), ('==', 'off')], join='or', type=int_or_off))
        parser.add_argument('--ge0',
            nargs=3,
            action=ActionOperators(expr=('>=', 0)))

        self.assertEqual(1.5, parser.parse_args(['--gt1.a.le4', '1.5']).gt1.a.le4)
        self.assertEqual(4.0, parser.parse_args(['--gt1.a.le4', '4.0']).gt1.a.le4)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--gt1.a.le4', '1.0']))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--gt1.a.le4', '5.5']))

        self.assertEqual(1.5, parser.parse_string('gt1:\n  a:\n    le4: 1.5').gt1.a.le4)
        self.assertEqual(4.0, parser.parse_string('gt1:\n  a:\n    le4: 4.0').gt1.a.le4)
        self.assertRaises(ParserError, lambda: parser.parse_string('gt1:\n  a:\n    le4: 1.0'))
        self.assertRaises(ParserError, lambda: parser.parse_string('gt1:\n  a:\n    le4: 5.5'))

        self.assertEqual(1.5, parser.parse_env(env={'APP_GT1__A__LE4': '1.5'}).gt1.a.le4)
        self.assertEqual(4.0, parser.parse_env(env={'APP_GT1__A__LE4': '4.0'}).gt1.a.le4)
        self.assertRaises(ParserError, lambda: parser.parse_env(env={'APP_GT1__A__LE4': '1.0'}))
        self.assertRaises(ParserError, lambda: parser.parse_env(env={'APP_GT1__A__LE4': '5.5'}))

        self.assertEqual(2, parser.parse_args(['--lt5.o.ge10.o.eq7', '2']).lt5.o.ge10.o.eq7)
        self.assertEqual(7, parser.parse_args(['--lt5.o.ge10.o.eq7', '7']).lt5.o.ge10.o.eq7)
        self.assertEqual(10, parser.parse_args(['--lt5.o.ge10.o.eq7', '10']).lt5.o.ge10.o.eq7)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--lt5.o.ge10.o.eq7', '5']))
        self.assertRaises(ParserError, lambda: parser.parse_args(['--lt5.o.ge10.o.eq7', '8']))

        self.assertEqual(9, parser.parse_args(['--gt0.o.off', '9']).gt0.o.off)
        self.assertEqual('off', parser.parse_args(['--gt0.o.off', 'off']).gt0.o.off)
        self.assertRaises(ParserError, lambda: parser.parse_args(['--gt0.o.off', 'on']))

        self.assertEqual([0, 1, 2], parser.parse_args(['--ge0', '0', '1', '2']).ge0)

        self.assertRaises(ValueError, lambda: parser.add_argument('--op1', action=ActionOperators))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op2', action=ActionOperators()))
        self.assertRaises(ValueError, lambda: parser.add_argument('--op3', action=ActionOperators(expr='<')))


def run_tests():
    tests = unittest.defaultTestLoader.loadTestsFromTestCase(JsonargparseTests)
    return unittest.TextTestRunner(verbosity=2).run(tests)


if __name__ == '__main__':
    sys.exit(not run_tests().wasSuccessful())
