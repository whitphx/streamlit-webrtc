# Development of `streamlit-webrtc`

## Set up
* Install `uv`
* Install dependencies
  ```shell
  $ uv sync
  ```
* Install pre-commit
  ```shell
  $ pre-commit install
  ```

## Development
* Edit `streamlit_webrtc/component.py` to set `_RELEASE = False` in order to show the frontend view served from a development server as below instead of the production build.
  * Do not commit this change. This setting is only for development.
  * If `_RELEASE = False` is set, the build command fails, which is described in the next section. See the `build` rule in `Makefile` and `release_check.py` for the details.
* Run the frontend dev server
  ```shell
  $ cd streamlit_webrtc/frontend
  $ pnpm dev
  ```
* In another shell, run `app.py`
  ```shell
  $ streamlit run home.py
  ```

## Changelog management and release
1. Run `scriv create` (`scriv create --edit` to open an editor) to create a changelog fragment for the next release. You should add a fragment for each pull request describing the changes made in the PR.
2. CI/CD automatically generates a changelog preview in a PR when a commit including changelog fragments is pushed to `main`. So merging a PR including changelog fragments triggers this process and creates a changelog preview PR.
3. After reviewing the changelog preview PR, merge it to `main`. This triggers another CI/CD process that creates a new release with new changelog entries based on the collected changelog fragments.

## Build
The following command is run to build the package during the automated release process in CI/CD described above.
When you want to run the build locally for development or test, you can directly use this command.
```
$ make build
```
