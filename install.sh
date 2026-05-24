#!/bin/bash
destination="/usr/local/bin"
while [ $# -gt 0 ]
do
  case "$1" in
    "--help"|"-h"|"-?")
      usage
      exit 0
      ;;
    "--destination"|"-d")
      shift
      destination="${1}"
      shift
      ;;
    *)
      echo "Ignoring unknwon parameter '${1}'"
      shift
      ;;
  esac
done

if [ ! -e "${HOME}/.config/update_zonefile.conf" ]; then
    touch "${HOME}/.config/update_zonefile.conf"
fi
chmod go-rwx "${HOME}/.config/update_zonefile.conf"

script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
sed "s#__src_folder__#${script_dir}#g" "${script_dir}/wrapper.sh" > "${destination}/update_zonefile.sh"
chmod +x "${destination}/update_zonefile.sh"
if [ ! -e "${script_dir}/.venv/bin/activate" ]; then
  python3 -m venv "${script_dir}/.venv"
  if [ ! -e "${script_dir}/.venv/bin/activate" ]; then
    echo "Error creating virtual environment"
    exit 1
  fi
  # shellcheck source=/dev/null
  source "${script_dir}/.venv/bin/activate"
  cd "${script_dir}" || exit 1
  pip install .
  if [ -e "${script_dir}/requirements.txt" ]; then
    pip install -r "${script_dir}/requirements.txt"
  fi
fi
