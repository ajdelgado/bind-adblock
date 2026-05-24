#!/bin/sh
podman run --mount type=bind,src=config/,target=/config -t --rm --name update_zonefile update_zonefile
