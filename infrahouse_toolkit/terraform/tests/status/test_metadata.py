import base64
import json

from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus


def test_metadata():
    backend = TFS3Backend("foo_backet", "path/to/tf.state")
    status = TFStatus(backend, True, RunResult(1, 2, 3), RunOutput("no stdout", "no stderr"))
    assert isinstance(status.metadata, str)
    assert json.loads(base64.b64decode(status.metadata))[backend.id]["add"] == 1
    assert json.loads(base64.b64decode(status.metadata))[backend.id]["change"] == 2
    assert json.loads(base64.b64decode(status.metadata))[backend.id]["destroy"] == 3
