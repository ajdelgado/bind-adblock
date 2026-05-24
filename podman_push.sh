#!/bin/bash
script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
repo="$(basename "${script_dir}")"
tag="${1}"
if [ -z "${tag}" ]; then
    git_tag=$(git describe --exact-match --tags)
    if [ "${git_tag}" == 'master' ] || [ "${git_tag}" == 'main' ] || [ -z "${git_tag}" ]; then
        echo "Change to a different git reference not 'master/main', since it will be used as tag for the container. Or pass a tag name as only parameter."
        exit 1
    fi
    tag="${git_tag}"
fi
echo "Building '${repo}:${tag}'..."
podman build --tag "${repo}:${tag}" .
echo "Tagging it to 'repos.susurrando.com/adelgado/${repo}:${tag}'..."
podman tag "${repo}:${tag}" "repos.susurrando.com/adelgado/${repo}:${tag}"
echo "Pushing it to 'repos.susurrando.com/adelgado/${repo}:${tag}'..."
podman push "repos.susurrando.com/adelgado/${repo}:${tag}"
tag=latest
echo "Building '${repo}:${tag}'..."
podman build --tag "${repo}:${tag}" .
echo "Tagging it to 'repos.susurrando.com/adelgado/${repo}:${tag}'..."
podman tag "${repo}:${tag}" "repos.susurrando.com/adelgado/${repo}:${tag}"
echo "Pushing it to 'repos.susurrando.com/adelgado/${repo}:${tag}'..."
podman push "repos.susurrando.com/adelgado/${repo}:${tag}"
