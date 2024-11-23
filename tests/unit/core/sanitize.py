from content_assistant_bot.api.handlers.common import sanitize_instagram_input

def test_sanitize_hashtags_and_mentions():
    input_text = "Check out #awesome @user!"
    expected_output = "Check out #awesome @user!"
    assert sanitize_instagram_input(input_text) == expected_output

def test_sanitize_instagram_url():
    input_text = "https://www.instagram.com/p/xyz123/"
    expected_output = "https://www.instagram.com/p/xyz123/"
    assert sanitize_instagram_input(input_text) == expected_output

def test_sanitize_non_instagram_url():
    input_text = "https://www.example.com"
    expected_output = "https://www.example.com"
    assert sanitize_instagram_input(input_text) == expected_output

def test_sanitize_no_special_characters():
    input_text = "Just a regular text"
    expected_output = "Just a regular text"
    assert sanitize_instagram_input(input_text) == expected_output
