import contextlib
import json
import time
from collections import defaultdict

import boa
import vyper

from config import Config
from db import get_mongo_client

sender = ""  # TODO: init actual sender address


class ContractsProvider:
    def __init__(self, db_connector):
        self._source = db_connector

    @contextlib.contextmanager
    def get_contracts(self):
        contracts = self._source.find({"ran": False})
        yield contracts
        self._source.update_many(
            {'_id': {'$in': [c['_id'] for c in contracts]}},
            {'ran': True}
        )


def get_input_params(types):
    # TODO: implement
    return []


def external_nonpayable_runner(contract, abi_func):
    func = getattr(contract, abi_func["name"])
    input_params = get_input_params(abi_func["inputs"])
    computation, output = func(*input_params)
    return computation, output


def compose_result(comp, ret) -> dict:
    # now we dump first ten slots only
    state = [comp.state.get_storage(bytes.fromhex(contract.address[2:]), i) for i in range(10)]

    # first 1280 bytes are dumped
    memory = comp.memory_read_bytes(0, 1280).hex()

    consumed_gas = comp.get_gas_used()

    return dict(state=state, memory=memory, consumed_gas=consumed_gas, return_value=ret)


def save_results(res):
    for gid, results in res.items():
        run_results_collection.insert_many({"generation_id": gid, "results": results})


if __name__ == "__main__":
    conf = Config()

    db_contracts = get_mongo_client(conf.db["host"], conf.db["port"])

    run_results_collection = db_contracts["run_results"]

    collections = [
        f"compilation_results_{vyper.__version__}_{c['name']}" for c in conf.compilers
    ]
    contracts_cols = (db_contracts[col] for col in collections)

    while True:
        contracts_providers = (ContractsProvider(contracts_col) for contracts_col in contracts_cols)
        reference_amount = len(collections)
        interim_results = defaultdict(list)
        for provider in contracts_providers:
            with provider.get_contracts() as contracts:
                for contract_desc in contracts:
                    at, _ = boa.env.deploy_code(
                        bytecode=bytes.fromhex(contract_desc["bytecode"][2:])
                    )

                    factory = boa.loads_abi(json.dumps(contract_desc["abi"]), name="Foo")
                    contract = factory.at(at)
                    for abi_item in contract_desc["abi"]:
                        if abi_item["type"] == "function" and abi_item["stateMutability"] == "nonpayable":
                            comp, ret = external_nonpayable_runner(contract, abi_item)

                            # well, now we save some side effects as json since it's not
                            # easy to pickle an object of abc.TitanoboaComputation
                            function_call_res = compose_result(comp, ret)
                            interim_results[contract_desc["_id"]].append(function_call_res)
        results = dict((_id, res) for _id, res in interim_results.items() if len(res) == reference_amount)
        save_results(results)

        time.sleep(2)  # wait two seconds before the next request
