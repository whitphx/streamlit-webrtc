#!/bin/bash

VERSION=${1:-}
if [ -z "${VERSION}" ]; then
  echo "VERSION must be set."
  exit -1
fi

if [[ $(git diff --stat) != '' ]]; then
  echo 'Git working tree is dirty.'
  exit -1
fi

echo "Set version to pyproject.toml"
poetry version ${VERSION}
CURRENT_VERSION=`poetry version -s`

echo "Add and commit pyproject.toml"
git add pyproject.toml
git commit -m "Version ${CURRENT_VERSION}"

GIT_TAG="v${CURRENT_VERSION}"
echo "Set git tag as ${GIT_TAG}"
git tag -a ${GIT_TAG} -m ${CURRENT_VERSION}
