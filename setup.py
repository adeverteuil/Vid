#!/usr/bin/python3


from distutils.core import setup


setup(
    name="Vid",
    version="0.1.0",
    description="A CLI video editor",
    author="Alexandre de Verteuil",
    author_email="alexandre.deverteuil@gmail.com",
    url="http://alexandre.deverteuil.net/",
    packages=["vid", "vid.test"],
    license="GPLv3",
    package_data={'vid.test': ["A roll/testsequence/*"]},
    )
