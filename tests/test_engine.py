from type_as_you_speak import engine


def test_hallucination_filter_preserves_real_words():
    assert (
        engine.clean_hallucinations("The meeting starts now. Thanks for watching!")
        == "The meeting starts now."
    )


def test_repetition_detection_distinguishes_a_loop_from_normal_speech():
    assert engine.has_repetition_loop(["hello", "hello", "hello", "hello"])
    assert not engine.has_repetition_loop(["the", "meeting", "starts", "now"])
