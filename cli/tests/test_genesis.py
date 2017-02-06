# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import argparse
import os
import tempfile
import shutil
import unittest

from sawtooth_cli.protobuf.batch_pb2 import BatchHeader
from sawtooth_cli.protobuf.batch_pb2 import Batch
from sawtooth_cli.protobuf.batch_pb2 import BatchList
from sawtooth_cli.protobuf.genesis_pb2 import GenesisData
from sawtooth_cli.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_cli.protobuf.transaction_pb2 import Transaction

from sawtooth_cli.admin_command import genesis
from sawtooth_cli.exceptions import CliException


class TestGenesisDependencyValidation(unittest.TestCase):

    def __init__(self, test_name):
        super().__init__(test_name)
        self._temp_dir = None
        self._parser = None

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp()

        self._parser = argparse.ArgumentParser()
        subparsers = self._parser.add_subparsers(title='subcommands',
                                                 dest='command')

        genesis.add_genesis_parser(subparsers, self._parser)

    def tearDown(self):
        shutil.rmtree(self._temp_dir)

    def _parse_command(self, batch_filenames):
        cmd_args = ['genesis', '-o',
                    os.path.join(self._temp_dir, 'genesis.batch')]
        cmd_args += batch_filenames

        return self._parser.parse_args(cmd_args)

    def _result_data(self):
        with open(os.path.join(self._temp_dir, "genesis.batch"), "rb") as f:
            output = GenesisData()
            output.ParseFromString(f.read())
            return output

    def test_validate_with_no_deps(self):
        batches = [self.make_batch('batch1',
                                   transaction('id1', []),
                                   transaction('id2', []),
                                   transaction('id3', [])),
                   self.make_batch('batch2',
                                   transaction('id4', []))]

        args = self._parse_command(batches)
        genesis.do_genesis(args)

        output = self._result_data()
        self.assertEqual(2, len(output.batches))

    def test_validate_with_deps_in_same_batch(self):
        batches = [self.make_batch('batch1',
                                   transaction('id1', []),
                                   transaction('id2', ['id1'])),
                   self.make_batch('batch2',
                                   transaction('id3', [])),
                   self.make_batch('batch3',
                                   transaction('id4', []))]

        args = self._parse_command(batches)
        genesis.do_genesis(args)

        output = self._result_data()
        self.assertEqual(3, len(output.batches))

    def test_validate_with_deps_in_across_batches(self):
        batches = [self.make_batch('batch1',
                                   transaction('id1', []),
                                   transaction('id2', []),
                                   transaction('id3', [])),
                   self.make_batch('batch2',
                                   transaction('id4', ['id1', 'id2']))]

        args = self._parse_command(batches)
        genesis.do_genesis(args)

        output = self._result_data()
        self.assertEqual(2, len(output.batches))

    def test_validation_fails_missing_dep(self):
        batches = [self.make_batch('batch1',
                                   transaction('id1', []),
                                   transaction('id2', []),
                                   transaction('id3', [])),
                   self.make_batch('batch2',
                                   transaction('id4', ['id11']))]

        args = self._parse_command(batches)
        with self.assertRaises(CliException):
            genesis.do_genesis(args)

    def test_validation_fails_self_dep(self):
        batches = [self.make_batch('batch1',
                                   transaction('id1', []),
                                   transaction('id2', ['id2']),
                                   transaction('id3', [])),
                   self.make_batch('batch2',
                                   transaction('id4', ['id1']))]

        args = self._parse_command(batches)
        with self.assertRaises(CliException):
            genesis.do_genesis(args)

    def test_validation_fails_out_of_order(self):
        batches = [self.make_batch('batch1',
                                   transaction('id1', []),
                                   transaction('id2', ['id4']),
                                   transaction('id3', [])),
                   self.make_batch('batch2',
                                   transaction('id4', ['id1']))]

        args = self._parse_command(batches)
        with self.assertRaises(CliException):
            genesis.do_genesis(args)

    def make_batch(self, batch_sig, *txns):
        txn_ids = [txn.header_signature for txn in txns]
        batch_header = BatchHeader(signer_pubkey='test_pubkey',
                                   transaction_ids=txn_ids).SerializeToString()

        batch = Batch(
            header=batch_header,
            header_signature=batch_sig,
            transactions=txns
        )

        batch_list = BatchList(batches=[batch])
        target_path = os.path.join(self._temp_dir, batch_sig + ".batch")
        with open(target_path, "wb") as f:
            filename = f.name
            f.write(batch_list.SerializeToString())

        return filename


def transaction(txn_sig, dependencies):
    header = TransactionHeader(
        signer_pubkey='test_pubkey',
        family_name='test_family',
        family_version='1.0',
        inputs=[],
        outputs=[],
        dependencies=dependencies,
        payload_encoding='application/protobuf',
        payload_sha512='some_sha512',
        batcher_pubkey='test_pubkey'
    ).SerializeToString()

    return Transaction(
        header=header,
        header_signature=txn_sig,
        payload=b'')
