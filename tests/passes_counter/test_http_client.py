import pytest
import requests

import src.passes_per_minute.passes_counter.http_client as http_client

"""
========================================================================================================================
_get_session
========================================================================================================================
"""


class TestGetSession:
    # Returns a Session object and caches it globally
    def test_returns_and_caches_session(self, monkeypatch):
        # Clear the global session cache – set _session to None
        monkeypatch.setattr(http_client, "_session", None)

        s1 = http_client._get_session()  # First call should create a new session
        s2 = http_client._get_session()  # Second call should return the same cached object

        # Verify that the returned object is an instance of requests.Session
        assert isinstance(s1, requests.Session)
        # Verify that both references point to the same object – cache works
        assert s1 is s2

    # Does not create a new Session when _session is already set
    def test_reuses_existing_session(self, monkeypatch):
        # Create a fake session object
        fake_session = object()
        # Insert it into http_client._session to simulate an existing cache
        monkeypatch.setattr(http_client, "_session", fake_session)

        # Call _get_session – it should return the existing session instead of creating a new one
        result = http_client._get_session()

        # Verify that the returned object is exactly the same as the cached one
        assert result is fake_session


"""
========================================================================================================================
get_json
========================================================================================================================
"""


def json():
    # Returned JSON data
    return {"ok": True}


class TestGetJson:
    # Success – the first request returns valid data
    def test_successful_fetch(self, monkeypatch):
        # Fake HTTP response – simulates a successful request (status 200)
        class FakeResp:
            status_code = 200

            @staticmethod
            def raise_for_status():
                # No error – request succeeded
                return None

            @staticmethod
            def json():
                return {"ok": True}

        # Fake HTTP session – records the last used arguments
        # so we can later verify how get() was called
        class FakeSession:
            def get(self, url, timeout, stream):
                self.last = (url, timeout, stream)  # Remember call arguments
                return FakeResp()

        # Create a fake session instance
        fake_sess = FakeSession()

        # Patch http_client._get_session to return fake_sess
        monkeypatch.setattr(http_client, "_get_session", lambda: fake_sess)

        # Call the tested function – should immediately return JSON data
        out = http_client.get_json("http://x", timeout=3, max_attempts=2)

        # Verify that the result is correct
        assert out == {"ok": True}

        # Verify that get() was called with correct arguments
        url, timeout, stream = fake_sess.last
        assert url == "http://x"
        assert timeout == 3
        assert stream is False

    # Error in get.raise_for_status – retries until success
    def test_retries_then_success(self, monkeypatch):
        # Call counter – tracks how many attempts were made
        calls = {"n": 0}

        # Fake HTTP response that fails a few times before succeeding
        class FakeResp:
            def __init__(self, fail_times):
                self.fail_times = fail_times  # number of failed attempts before success

            def raise_for_status(self):
                # Increment attempt counter
                calls["n"] += 1
                # Fail until reaching fail_times
                if calls["n"] <= self.fail_times:
                    raise requests.exceptions.HTTPError("fail")
                # After fail_times – success
                return None

            @staticmethod
            def json():
                # Return data with the attempt number
                return {"ok": calls["n"]}

            @property
            def status_code(self):
                # Simulated response status – always 200 (OK)
                return 200

        # Fake HTTP session – returns FakeResp that “fails” twice, then succeeds
        class FakeSession:
            @staticmethod
            def get(url, timeout, stream):
                return FakeResp(fail_times=2)

        # Patch _get_session to return our fake session
        monkeypatch.setattr(http_client, "_get_session", lambda: FakeSession())

        # Patch sleep to avoid real waiting between retries
        monkeypatch.setattr(http_client.time, "sleep", lambda _t: None)

        # Call get_json – should succeed on the 3rd attempt (2 failures + 1 success)
        out = http_client.get_json("http://retry", max_attempts=5)

        # Verify that the result came from the 3rd attempt
        assert out == {"ok": 3}
        # Verify that exactly 3 attempts were made
        assert calls["n"] == 3

    # Persistent error – after max_attempts, raises an exception
    def test_raises_after_all_attempts(self, monkeypatch):
        # Fake HTTP response that always raises a connection error
        class FakeResp:
            status_code = 500

            def raise_for_status(self):
                # Every call results in a connection error
                raise requests.exceptions.ConnectionError("nope")

            @staticmethod
            def json():
                # Normally would return JSON data,
                # but here it will never be called
                return {"never": "called"}

        # Fake HTTP session — always returns FakeResp
        class FakeSession:
            @staticmethod
            def get(url, timeout, stream):
                return FakeResp()

        # Patch real _get_session to return fake session
        monkeypatch.setattr(http_client, "_get_session", lambda: FakeSession())

        # Patch sleep to skip waiting between retries
        monkeypatch.setattr(http_client.time, "sleep", lambda _t: None)

        # Expect get_json() to raise a RuntimeError after all retry attempts fail
        # Capture the raised exception information in 'excinfo'
        with pytest.raises(RuntimeError) as excinfo:
            http_client.get_json("http://fail", max_attempts=3)

        # Verify that the underlying cause (__cause__) of the RuntimeError is a ConnectionError raised during the HTTP request
        assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
        # Verify that the RuntimeError message matches the expected failure message
        assert str(excinfo.value) == "HTTP GET failed after 3 attempts"

    # Handle multiple types of errors (ChunkedEncodingError, ReadTimeout, etc.)
    @pytest.mark.parametrize(
        "exc_type",
        [
            "ChunkedEncodingError",
            "ConnectionError",
            "ReadTimeout",
            "HTTPError",
        ],
    )
    def test_different_exceptions_are_caught(self, monkeypatch, exc_type):
        # Convert error name (e.g. "ConnectionError") to actual exception class from requests.exceptions
        exc_cls = getattr(requests.exceptions, exc_type)

        # Fake HTTP response that simulates a failed request
        class FakeResp:
            status_code = 500

            def raise_for_status(self):
                # Always raises the given exception
                raise exc_cls("bad")

            @staticmethod
            def json():
                # Normally would return JSON data,
                # but here it will never be called
                return {"bad": True}

        # Fake HTTP session — always returns FakeResp
        class FakeSession:
            @staticmethod
            def get(url, timeout, stream):
                return FakeResp()

        # Patch _get_session to return our fake session
        monkeypatch.setattr(http_client, "_get_session", lambda: FakeSession())

        # Patch sleep to skip waiting between retries
        monkeypatch.setattr(http_client.time, "sleep", lambda _t: None)

        # Expect a RuntimeError to be raised by get_json()
        # and capture the exception info in 'excinfo'
        with pytest.raises(RuntimeError) as excinfo:
            http_client.get_json("http://fail", max_attempts=1)

        # Verify that the original cause of the RuntimeError is the specific exception type we simulated (exc_cls)
        assert isinstance(excinfo.value.__cause__, exc_cls)

        # Verify that the RuntimeError message matches the expected text
        assert str(excinfo.value) == "HTTP GET failed after 1 attempts"
