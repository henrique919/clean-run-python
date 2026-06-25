from setuptools import setup


def patch_app_py() -> None:
    print("CleanRun build patch package installed", flush=True)


patch_app_py()

setup(name="cleanrun-render-build-patch", version="0.0.3", py_modules=["sitecustomize"])
