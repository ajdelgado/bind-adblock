#!/bin/bash
app=$(basename "${0}" .sh)
script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
if [ ! -d "${script_dir}/.venv" ]; then
    python3 -m venv "$script_dir/.venv"
fi
# shellcheck source=/dev/null
source "$script_dir/.venv/bin/activate"
if [ "${1}" == "--update" ] || [ ! -x "${script_dir}/.venv/bin/python3" ] || [ ! -x "${script_dir}/.venv/bin/${app}.py" ] || ! "${app}.py" --help 2> /dev/null; then
    if [ -r "$script_dir/requirements.txt" ]; then
        pip install -r "$script_dir/requirements.txt" > /dev/null
    fi
    pip install "$script_dir/" > /dev/null
fi
"${app}" "${@}"
