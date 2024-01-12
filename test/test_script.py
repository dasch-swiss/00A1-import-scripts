from collections.abc import Iterator
from pathlib import Path
import re
import subprocess

from dsp_tools import excel2xml
from lxml import etree
import pytest

import import_script


@pytest.fixture(scope="module")
def generated_xml_file() -> Iterator[Path]:
    """Yield the generated XML file as fixture, and delete it afterwards"""
    xml_file = Path("data-processed.xml")
    yield xml_file
    xml_file.unlink(missing_ok=True)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_script_output(generated_xml_file: Path) -> None:
    """Execute the import script and compare the generated XML with the expected XML"""
    import_script.main()
    with open("test/expected.xml", encoding="utf-8") as f:
        xml_expected = _derandomize_xsd_id(f.read(), multiple_occurrences=True)
    with open(generated_xml_file, encoding="utf-8") as f:
        xml_returned = _derandomize_xsd_id(f.read(), multiple_occurrences=True)
    assert _sort_xml_by_id(xml_expected) == _sort_xml_by_id(xml_returned)


def test_create() -> None:
    """Create the project on the DSP server"""
    subprocess.run("dsp-tools create import_project.json".split(), check=True)


def test_upload(generated_xml_file: Path) -> None:
    """Upload the created XML to the DSP server"""
    subprocess.run(f"dsp-tools xmlupload {generated_xml_file}".split(), check=True)


def _sort_xml_by_id(xml: str) -> str:
    """Sort the elements in the XML by their ID"""
    xml_tree = etree.fromstring(xml.encode("utf-8"))
    for elem in xml_tree.iter():
        elem[:] = sorted(elem, key=lambda x: x.attrib.get("id", ""))
    return etree.tostring(xml_tree).decode("utf-8")


def _derandomize_xsd_id(
    string: str,
    multiple_occurrences: bool = False,
) -> str:
    """
    In some contexts, the random component of the output of make_xsd_id_compatible() is a hindrance,
    especially for testing.
    This method removes the random part,
    but leaves the other modifications introduced by make_xsd_id_compatible() in place.
    This method's behaviour is defined by the example in the "Examples" section.

    Args:
        string: the output of make_xsd_id_compatible()
        multiple_occurrences: If true, string can be an entire XML document, and all occurrences will be removed

    Raises:
        Exception: if the input cannot be derandomized

    Returns:
        the derandomized string

    Examples:
        >>> id_1 = make_xsd_id_compatible("Hello!")
        >>> id_2 = make_xsd_id_compatible("Hello!")
        >>> assert _derandomize_xsd_id(id_1) == _derandomize_xsd_id(id_2)
    """
    if not isinstance(string, str) or not excel2xml.check_notna(string):
        raise Exception(f"The input '{string}' cannot be derandomized.")

    uuid4_regex = r"[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}"
    if multiple_occurrences:
        return re.subn(uuid4_regex, "", string, flags=re.IGNORECASE)[0]
    else:
        return re.sub(uuid4_regex, "", string, re.IGNORECASE)


if __name__ == "__main__":
    pytest.main([__file__])
