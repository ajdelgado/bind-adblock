#!/bin/bash

SCRIPT_DIRNAME=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

virtual_env_dir="${1}"
shift
if [ ! -d "${virtual_env_dir}" ]; then
    echo "First argument is the directory with the Python virtual environment"
    exit 1
fi

source "${virtual_env_dir}/bin/activate"
"${SCRIPT_DIRNAME}/update-zonefile.py" $*
