"""
Arguments for the script are:
    -v or --version         Solidity version to be used to compile the contracts. If
                            blank, the script uses the latest hard-coded version
                            specified within the script.

    -f or --filename        If left blank, all .sol files will be compiled and the
                            respective contract data will be generated. Pass in a
                            specific ``.sol`` filename here to compile just one file.


To run the script, you will need the ``py-solc-x`` library for compiling the files
as well as ``black`` for linting. You can install those independently or install the
full ``[dev]`` package extra as shown below.

.. code:: sh

    $ pip install "web3[dev]"

The following example compiles all the contracts and generates their respective
contract data that is used across our test files for the test suites. This data gets
generated within the ``contract_data`` subdirectory within the ``contract_sources``
folder.

.. code-block:: bash

    $ cd ../web3.py/web3/_utils/contract_sources
    $ python compile_contracts.py -v 0.8.17
    Compiling OffchainLookup
    ...
    ...
    reformatted ...

To compile and generate contract data for only one ``.sol`` file, specify using the
filename with the ``-f`` (or ``--filename``) argument flag.

.. code-block:: bash

    $ cd ../web3.py/web3/_utils/contract_sources
    $ python compile_contracts.py -v 0.8.17 -f OffchainLookup.sol
    Compiling OffchainLookup.sol
    reformatted ...
"""

import argparse
import os
import re
from typing import (
    Any,
    Dict,
    List,
)

import solcx

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument(
    "-v", "--version", help="Solidity version for compiling contracts."
)
arg_parser.add_argument(
    "-f",
    "--filename",
    help="(optional) The filename if only one file is to be compiled - "
    "otherwise all .sol files will be compiled at once.",
)
user_args = arg_parser.parse_args()

LATEST_AVAILABLE_SOLIDITY_VERSION = sorted(solcx.get_compilable_solc_versions())[-1]
# establish Solidity version from user-provided arg or use latest available version
user_sol_version = user_args.version

solidity_version = (
    user_sol_version if user_sol_version else LATEST_AVAILABLE_SOLIDITY_VERSION
)
solcx.install_solc(solidity_version)
solcx.set_solc_version(solidity_version)


# compile just the .sol file specified or all .sol files
all_dot_sol_files = [f for f in os.listdir(os.getcwd()) if f.endswith(".sol")]
user_filename = user_args.filename
files_to_compile = [user_filename] if user_filename else all_dot_sol_files


def _compile_dot_sol_files(dot_sol_filename: str) -> Dict[str, Any]:
    compiled = solcx.compile_files(
        [f"./{dot_sol_filename}"],
        output_values=["abi", "bin", "bin-runtime"],
    )
    return compiled


def _get_compiled_contract_data(
    sol_file_output: Dict[str, Dict[str, str]],
    dot_sol_filename: str,
    contract_name: str = None,
) -> Dict[str, str]:
    if not contract_name:
        contract_name = dot_sol_filename.replace(".sol", "")

    contract_data = None
    for key in sol_file_output.keys():
        if f":{contract_name}" in key:
            contract_data = sol_file_output[key]
    if not contract_data:
        raise Exception(f"Could not find compiled data for contract: {contract_name}")

    contract_data["bin"] = f"0x{contract_data['bin']}"
    contract_data["bin-runtime"] = f"0x{contract_data['bin-runtime']}"

    return contract_data


contracts_in_file = {}


def compile_files(file_list: List[str]) -> None:
    for filename in file_list:
        with open(os.path.join(os.getcwd(), filename)) as f:
            dot_sol_file = f.readlines()

        contract_names = []

        for line in dot_sol_file:
            if all(_ in line for _ in ["contract", "{"]) and "abstract" not in line:
                start_index = line.find("contract ") + len("contract ")
                end_index = line[start_index:].find(" ") + start_index
                contract_name = line[start_index:end_index]
                contract_names.append(contract_name)

        contracts_in_file[filename] = contract_names

    for dot_sol_filename in contracts_in_file.keys():
        filename_no_extension = dot_sol_filename.replace(".sol", "")
        split_and_lowercase = [
            i.lower() for i in re.split(r"([A-Z][a-z]*)", filename_no_extension) if i
        ]
        python_filename = f"{'_'.join(split_and_lowercase)}.py"
        python_file_path = os.path.join(os.getcwd(), "contract_data", python_filename)
        try:
            # clean up existing files
            os.remove(python_file_path)
        except FileNotFoundError:
            pass
        print(f"compiling {dot_sol_filename}")
        compiled_dot_sol_data = _compile_dot_sol_files(dot_sol_filename)
        with open(python_file_path, "w") as f:
            f.write(f'"""\nGenerated by `{os.path.basename(__file__)}` script.\n')
            f.write(f'Compiled with Solidity v{solidity_version}.\n"""\n\n')

            for c in contracts_in_file[dot_sol_filename]:
                c_name_split_and_uppercase = [
                    i.upper() for i in re.split(r"([A-Z0-9][a-z0-9]*)", c) if i
                ]
                contract_upper = "_".join(c_name_split_and_uppercase)

                c_data = _get_compiled_contract_data(
                    compiled_dot_sol_data, dot_sol_filename, c
                )

                contract_source = (
                    f"# source: web3/_utils/contract_sources/{dot_sol_filename}:{c}"
                )
                if len(contract_source) > 88:
                    contract_source += "  # noqa: E501"

                f.write(f"{contract_source}\n")
                f.write(
                    f'{contract_upper}_BYTECODE = "{c_data["bin"]}"  # noqa: E501\n'
                )
                f.write(
                    f'{contract_upper}_RUNTIME = "{c_data["bin-runtime"]}"  # noqa: E501\n'
                )
                f.write(f"{contract_upper}_ABI = {c_data['abi']}\n")
                f.write(contract_upper + "_DATA = {\n")
                f.write(f'    "bytecode": {contract_upper}_BYTECODE,\n')
                f.write(f'    "bytecode_runtime": {contract_upper}_RUNTIME,\n')
                f.write(f'    "abi": {contract_upper}_ABI,\n')
                f.write("}\n\n\n")


compile_files(files_to_compile)
os.system(f"black {os.getcwd()}")
