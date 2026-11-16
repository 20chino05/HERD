from herd_ai.models import MODEL_CATALOG, input_size_from_name, model_path


def test_input_size_is_parsed_from_st_model_file_names():
    assert input_size_from_name("yolov8n_256_quant_pc_uf_od_coco-person.tflite") == 256
    assert input_size_from_name("yolov8n_416_quant_pc_uf_od_coco-person") == 416
    assert input_size_from_name("st_yoloxn_d033_w025_320_int8.tflite") == 320


def test_catalog_lists_the_four_yolov8n_person_models_with_github_urls():
    yolo = [m for m in MODEL_CATALOG if m.family == "yolov8n"]
    assert sorted(m.input_size for m in yolo) == [192, 256, 320, 416]
    for m in yolo:
        assert m.url.startswith("https://raw.githubusercontent.com/stm32-hotspot/ultralytics/")
        assert m.url.endswith(m.filename)
        assert m.filename.endswith(".tflite")


def test_catalog_includes_st_osnet_reid_models_without_detection_ap():
    osnet = [m for m in MODEL_CATALOG if m.family == "osnet"]
    assert sorted(m.filename for m in osnet) == [
        "osnet_a025_256_128_tfs_int8.tflite",
        "osnet_a100_256_128_tfs_int8.tflite",
    ]
    for m in osnet:
        assert m.st_ap50_percent is None  # a re-ID model has no detection AP
        assert m.st_n6_ms and m.st_n6_ms > 0
        assert "re_identification/osnet/" in m.url


def test_model_path_resolves_inside_the_models_dir():
    p = model_path("yolov8n_256_quant_pc_uf_od_coco-person.tflite")
    assert p.name == "yolov8n_256_quant_pc_uf_od_coco-person.tflite"
    assert p.parent.name == "models"
