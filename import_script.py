import warnings
from pathlib import Path

import pandas as pd
import regex

from dsp_tools import excel2xml


def main() -> None:
    """
    main method: all code must be inside this method
    """
    # general preparation
    # -------------------
    path_to_json = "import_project.json"
    main_df = pd.read_csv("data_raw.csv", dtype="str", sep=",")  # or: pd.read_excel("*.xls(x)", dtype="str")

    # remove rows without usable values (prevents Errors when there are empty rows at the end of the file)
    main_df = main_df.map(
        lambda x: x if pd.notna(x) and regex.search(r"[\p{L}\d_!?]", str(x), flags=regex.U) else pd.NA
    )
    main_df = main_df.dropna(axis="index", how="all")

    # create the root tag <knora> and append the permissions
    root = excel2xml.make_root(shortcode="00A1", default_ontology="import")
    root = excel2xml.append_permissions(root)

    # create list mappings
    # --------------------
    # For every node of the list "category", this dictionary maps the German label to the node name.
    category_labels_to_names = excel2xml.create_json_list_mapping(
        path_to_json=path_to_json,
        list_name="category",
        language_label="de",
    )
    # For every node of the list "category", this dictionary maps similar entries of the Excel column to the node name.
    # When you run this script, two warnings appear, saying that "Säugetiere" and "Kunstwerk" couldn't be matched.
    # Luckily, these two are covered in category_labels_to_names.
    category_excel_values_to_names = excel2xml.create_json_excel_list_mapping(
        path_to_json=path_to_json,
        list_name="category",
        excel_values=main_df["Category"],
        sep=",",
    )

    # create resources of type ":Image2D"
    # -----------------------------------
    # create a dict that keeps the IDs of the created resources,
    # retrieve all files from the "images" folder that don't start with "~$" or ".",
    image2d_labels_to_ids = {}
    all_images = [x for x in Path("images").glob("*") if not regex.search(r"^~$|^\.", x.name)]

    # iterate through all images, and create an ":Image2D" for every image file
    for img in all_images:
        # keep a reference to this ID in the dict
        resource_label = img.name
        resource_id = excel2xml.make_xsd_id_compatible(resource_label)
        image2d_labels_to_ids[resource_label] = resource_id

        resource = excel2xml.make_resource(label=resource_label, restype=":Image2D", id=resource_id)
        resource.append(excel2xml.make_bitstream_prop(img, check=True))
        resource.append(excel2xml.make_text_prop(":hasTitle", resource_label))
        root.append(resource)

    # create resources of type ":Object"
    # ----------------------------------
    # create a dict that keeps the IDs of the created resources
    object_labels_to_ids = {}

    # iterate through all rows of your data source, in pairs of (row-number, row)
    for i, row in main_df.iterrows():
        index = int(str(i))  # convert the index to an integer

        # keep a reference to this ID in the dict
        resource_label = row["Object"]
        resource_id = excel2xml.make_xsd_id_compatible(resource_label)
        object_labels_to_ids[resource_label] = resource_id

        resource = excel2xml.make_resource(label=resource_label, restype=":Object", id=resource_id)

        # check every existing ":Image2D" resource, if there is an image that belongs to this object
        for img_label, img_id in image2d_labels_to_ids.items():
            # check if the label of ":Object" is contained in the label of ":Image2D"
            if resource_label in img_label:
                # create a resptr-link to the ID of the ":Image2D" resource
                resource.append(excel2xml.make_resptr_prop(":hasImage", img_id))

        # add a text property with the simple approach
        resource.append(excel2xml.make_text_prop(":hasName", row["Title"]))

        # add a text property, overriding the default values for "permissions" and "encoding"
        resource.append(
            excel2xml.make_text_prop(
                ":hasDescription",
                excel2xml.PropertyElement(
                    value=row["Description"],
                    permissions="prop-restricted",
                    comment="comment to 'Description'",
                    encoding="xml",
                ),
            )
        )

        # get "category" list nodes: split the cell into a list of values...
        category_labels = [x.strip() for x in row["Category"].split(",")]
        # ...look up every value in "category_labels_to_names",
        # and if it's not there, in "category_excel_values_to_names"...
        category_names = [
            category_labels_to_names.get(x, category_excel_values_to_names.get(x)) for x in category_labels
        ]
        # ...filter out the None values...
        category_names_str = [x for x in category_names if x is not None]
        # ...create the <list-prop> with the correct names of the list nodes
        resource.append(excel2xml.make_list_prop("category", ":hasCategory", category_names_str))

        if excel2xml.check_notna(row["Public"]):
            resource.append(excel2xml.make_boolean_prop(":isPublic", row["Public"]))
        if excel2xml.check_notna(row["Color"]):
            resource.append(excel2xml.make_color_prop(":hasColor", row["Color"]))
        potential_date = excel2xml.find_date_in_string(row["Date"])
        if potential_date:
            resource.append(excel2xml.make_date_prop(":hasDate", potential_date))
        else:
            warnings.warn(f"Error in row {index + 2}: The column 'Date' should contain a date!")
        if excel2xml.check_notna(row["Time"]):
            resource.append(excel2xml.make_time_prop(":hasTime", row["Time"]))
        if excel2xml.check_notna(row["Weight (kg)"]):
            resource.append(excel2xml.make_decimal_prop(":hasWeight", row["Weight (kg)"]))
        if excel2xml.check_notna(row["Location"]):
            resource.append(excel2xml.make_geoname_prop(":hasLocation", row["Location"]))
        if excel2xml.check_notna(row["URL"]):
            resource.append(excel2xml.make_uri_prop(":hasExternalLink", row["URL"]))

        root.append(resource)

    # Annotation, Region, Link
    # ------------------------
    # These special resource classes are DSP base resources,
    # that's why they use DSP base properties without prepended colon.
    # See the docs for more details:
    # https://docs.dasch.swiss/latest/DSP-TOOLS/file-formats/xml-data-file/#dsp-base-resources-and-base-properties-to-be-used-directly-in-the-xml-file
    annotation = excel2xml.make_annotation("Annotation to Anubis", "annotation_to_anubis")
    annotation.append(
        excel2xml.make_text_prop(
            "hasComment",
            excel2xml.PropertyElement("Date and time are invented, like for the other resources.", encoding="xml"),
        )
    )
    annotation.append(excel2xml.make_resptr_prop("isAnnotationOf", object_labels_to_ids["Anubis"]))
    root.append(annotation)

    region = excel2xml.make_region("Region of the Meteorite image", "region_of_meteorite")
    region.append(excel2xml.make_text_prop("hasComment", excel2xml.PropertyElement("This is a comment", encoding="xml")))
    region.append(excel2xml.make_color_prop("hasColor", "#5d1f1e"))
    region.append(excel2xml.make_resptr_prop("isRegionOf", image2d_labels_to_ids["GibeonMeteorite.jpg"]))
    region.append(
        excel2xml.make_geometry_prop(
            "hasGeometry",
            '{"type": "rectangle", "lineColor": "#ff3333", "lineWidth": 2, '
            '"points": [{"x": 0.08, "y": 0.16}, {"x": 0.73, "y": 0.72}], "original_index": 0}',
        )
    )
    root.append(region)

    link = excel2xml.make_link("Link between BM1888-0601-716 and Horohoroto", "link_BM1888-0601-716_horohoroto")
    link.append(excel2xml.make_text_prop("hasComment", excel2xml.PropertyElement("This is a comment", encoding="xml")))
    link.append(
        excel2xml.make_resptr_prop(
            "hasLinkTo",
            [object_labels_to_ids["BM1888-0601-716"], object_labels_to_ids["Horohoroto"]],
        )
    )
    root.append(link)


    # Video with a Segment
    # --------------------
    # Videos and audios are normal resources...
    video = excel2xml.make_resource("Publicly available video", ":VideoObject", "video_1")
    video.append(excel2xml.make_bitstream_prop("videos/my_video.mp4"))
    root.append(video)

    # ... but the segments behave differently:
    segment = excel2xml.make_video_segment("The first 5 seconds of my video", "segment_1")
    segment.append(excel2xml.make_isSegmentOf_prop("video_1"))
    segment.append(excel2xml.make_hasSegmentBounds_prop(segment_start=0, segment_end=5))
    segment.append(excel2xml.make_hasTitle_prop("Intro of my video"))
    segment.append(excel2xml.make_hasComment_prop("Video segments can also have comments"))
    segment.append(excel2xml.make_hasDescription_prop("This segments spans the first 5 seconds of my video"))
    segment.append(excel2xml.make_hasKeyword_prop("publicly available video"))
    segment.append(excel2xml.make_relatesTo_prop(object_labels_to_ids["Horohoroto"]))
    root.append(segment)

    # audio segments are identical, just replace "video" by "audio"


    # write file
    # ----------
    excel2xml.write_xml(root, "data-processed.xml")


if __name__ == "__main__":
    main()
