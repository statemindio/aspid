# Vyper Structure aware fuzzing

This repository provides a comprehensive fuzzing framework designed to test the `Vyper` compiler. By generating a wide range of test cases and verifying results across different compiler versions and configurations, the framework aims to identify inconsistencies, bugs, and potential optimizations within `Vyper`. The framework leverages coverage-guided source generation, differential testing, and runtime validation to test `Vyper`’s handling of diverse code constructs.

## Key features

- `Vyper` source code generation

- Differential testing across compiler versions configurations, and interpreters

- Configurable `proto` templates for targeted testing

- Modular design and customization of services implementations

- Automated result verification and validation

- Scalable distributed task management

## Debug start-up

To set up the project for test running and debugging follow the guide [here](./howto_run.md).

## Documentation
The project consists of a few parts described below:

* [`fuzz`](/fuzz/README.md)
  * [`converters`](fuzz/converters/README.md)
  * [`generators`](fuzz/generators/README.md)
  * [`helpers`](fuzz/helpers/README.md)
  * [`runners`](fuzz/runners/README.md)
  * [`verifiers`](fuzz/verifiers/README.md)
