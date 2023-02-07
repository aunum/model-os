import logging

from modelos.scm import SCM


def test_scm():
    scm = SCM()
    output_path = scm.archive()
    logging.info(f"archive output {output_path}")

    found = scm.find_archive()

    assert found == output_path
