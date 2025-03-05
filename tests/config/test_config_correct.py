import pcot.config


def test_config_is_correct_for_testing():
    assert pcot.config.default_camera == "PANCAM", "Config Default.camera should be PANCAM or the some tests will fail"