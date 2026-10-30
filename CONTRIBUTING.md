# Contributing

Contributions are welcome.
For a substantial change, open an issue first to discuss the approach.

## Develop and test

Follow the [engineering workflow](README.md#engineering-workflow) to set up a checkout, prepare package resources, and run tests.
Choose tests relevant to your change and describe what you ran in the pull request.
Run the repository checks before submitting:

```console
pixi run pre-commit run --all-files
```

The hooks check REUSE metadata and format prose with Snapper.
Review and include any formatting changes they make.

## Submit a pull request

Create a branch, make focused commits, and open a pull request against `main`.
Use a [Conventional Commit](https://www.conventionalcommits.org/en/v1.0.0/) subject and describe the problem, the change, and its validation in the pull request.
Link any related issue and explain known limitations or follow-up work.

## Licensing

Contributions are subject to the terms described in [LICENSES.md](LICENSES.md).
Preserve third-party copyright and license notices, and add accurate REUSE annotations and license texts when needed.
Do not assume that publicly available media can be redistributed; document its rights before including it.
