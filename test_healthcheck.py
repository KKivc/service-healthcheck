from healthcheck import check_service
from unittest.mock import patch, Mock

def test_success():
    with patch('healthcheck.requests.get') as fake_get:
        fake_get.return_value = Mock(status_code = 200)
        s, r = check_service({'name': 'abc', 'url': 'http://www.abc.com'})
        assert s == True and r == 200

def test_error():
    with patch('healthcheck.requests.get') as fake_get:
        fake_get.return_value = Mock(status_code = 500)
        s, r = check_service({'name': 'abc', 'url': 'http://www.abc.com'})
        assert s == False and r == 500

def test_exception():
    with patch('healthcheck.requests.get') as fake_get:
        fake_get.side_effect = Exception('连接错误')
        s, r = check_service({'name': 'abc', 'url': 'http://www.abc.com'})
        assert s == False and r == '连接错误'