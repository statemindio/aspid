import json
import logging

import atheris
import atheris_libprotobuf_mutator
from google.protobuf.json_format import MessageToJson

import vyperProtoNew_pb2
from config import Config
from db import get_mongo_client
from input_generation import InputGenerator, InputStrategy
from json_encoders import ExtendedEncoder
from queue_managers import QueueManager, MultiQueueManager

with atheris.instrument_imports():
    import sys
    import vyper
    from converters.typed_converters import TypedConverter

__version__ = "0.1.3"  # same version as images' one

conf = Config()
# might throw an error if verbosity is not a correct logging level
logger_level = getattr(logging, conf.verbosity)
logger = logging.getLogger("generator")
logging.basicConfig(format='%(name)s:%(levelname)s:%(asctime)s:%(message)s', level=logger_level)
logger.info("Starting version %s", __version__)

db_client = get_mongo_client(conf.db["host"], conf.db["port"])

run_with_queue = conf.use_queue

logger.info("Using queue %s", run_with_queue)

if run_with_queue:
    qm = MultiQueueManager(queue_managers=[
        QueueManager(
            q_params["host"],
            q_params["port"],
            q_params["queue_name"],
            logger
        )
        for q_params in conf.compiler_queues])

input_generator = InputGenerator()

@atheris.instrument_func
def TestOneProtoInput(msg):
    data = {
        "json_msg": MessageToJson(msg),
        "generation_result": None,
        "compilation_result": None,
        "error_type": None,
        "error_message": None,
        "generator_version": __version__,
    }

    logger.debug("Converting: %s", MessageToJson(msg))

    c_log = db_client["compilation_log"]
    f_log = db_client['failure_log']
    try:
        proto = TypedConverter(msg)
        proto.visit()
    except Exception as e:
        converter_error = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "json_msg": MessageToJson(msg),
        }
        f_log.insert_one(converter_error)

        logger.critical("Converter has crashed: %s", converter_error)
        raise e  # Do we actually want to fail here?
    data["generation_result"] = proto.result
    try:
        c_result = vyper.compile_code(proto.result)
        data["compilation_result"] = c_result
    except Exception as e:
        data["error_type"] = type(e).__name__
        data["error_message"] = str(e)

    logger.debug("Compilation result: %s", data)

    input_values = dict()
    for name, types in proto.function_inputs.items():
        for i in conf.input_strategies:
            input_generator.change_strategy(InputStrategy(i))

            if input_values.get(name, None) is None:
                input_values[name] = []
            input_values[name].append(input_generator.generate(types))

    input_values = json.dumps(input_values, cls=ExtendedEncoder)
    logger.debug("Generated inputs: %s", input_values)

    data["function_input_values"] = input_values
    ins_res = c_log.insert_one(data)

    if run_with_queue:
        message = {
            "_id": str(ins_res.inserted_id),
            "generation_result": proto.result,
            "function_input_values": input_values,
            "json_msg": MessageToJson(msg),
            "generator_version": __version__,
        }
        qm.publish(**message)
    else:
        compiler_version = f"{vyper.__version__.replace('.', '_')}"
        for c in conf.compilers:
            data[f"compiled_{compiler_version}_{c['name']}"] = False
    # Creating the result entry, so there's no race condition in runners
    db_client["run_results"].insert_one({'generation_id': str(ins_res.inserted_id)})

if __name__ == '__main__':
    atheris_libprotobuf_mutator.Setup(
        sys.argv, TestOneProtoInput, proto=vyperProtoNew_pb2.Contract)
    atheris.Fuzz()
