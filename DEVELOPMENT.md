# Development of streamlit-webrtc

## Development
* Edit `streamlit_webrtc/__init__.py` to set `_RELEASE = False` in order to show the frontend view served from a development server as below instead of a production build.
  * Do not commit this change. This setting is only for development.
  * If `_RELEASE = False` is set, the build command described in the next section fails. See `pkg/build` rule in `Makefile` and `release_check.py` for the details.
* Run frontend dev server
  ```shell
  $ cd streamlit_webrtc/frontend
  $ npm start
  ```
* In another shell, run `app.py`
  ```shell
  $ streamlit run app.py
  ```

## Release
1. Edit `CHANGELOG.md` and commit it.
2. Set the next version. The script below updates the package version defined in `pyproject.toml` and creates a new Git tag representing this release.
   ```
   $ ./scripts/bump-version.sh <version>
   ```
   `patch`, `minor`, or `major` can be used as `<version>`.
3. Push the commit with the tag to GitHub. After pushing the tag, CI/CD automatically deploy the release.
   ```
   $ git push --tags
   ```

## Build
The following command is run to build the package during the automated release flow described above.
When you want to run the build locally for development or test, you can directly use this command.
```
$ make pkg/build
```
