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
  * If `_RELEASE = False` is set, the build command fails, which is described in the next section. See the `pkg/build` rule in `Makefile` and `release_check.py` for the details.
* Run the frontend dev server
  ```shell
  $ cd streamlit_webrtc/frontend
  $ pnpm dev
  ```
* In another shell, run `app.py`
  ```shell
  $ streamlit run home.py
  ```

## Release
1. Edit `CHANGELOG.md` and commit it.
2. Set the next version with the following command, which creates a new Git tag representing this release.
   ```
   $ bump-my-version bump <version> --tag --commit --commit-args='--allow-empty'
   ```
   NOTE: `patch`, `minor`, or `major` can be used as `<version>`.
3. Push the commit with the tag to GitHub. After pushing the tag, CI/CD automatically deploys the release.
   ```
   $ git push
   $ git push --tags
   ```

## Build
The following command is run to build the package during the automated release process in CI/CD described above.
When you want to run the build locally for development or test, you can directly use this command.
```
$ make pkg/build
```
