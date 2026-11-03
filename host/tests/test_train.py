import math
from pathlib import Path

from frostbite_host.train import RunState, TrainWatcher, parse_line

FIX = Path(__file__).parent / "fixtures" / "train"


def run_file(name, **kw):
    sent = []
    clock = [1000.0]
    w = TrainWatcher(str(FIX / name), "my-model", sent.append, clock=lambda: clock[0], **kw)
    w.feed_text((FIX / name).read_text())
    return w, sent, clock


def test_parse_text_line():
    i = parse_line("Epoch 2/5 | step 400 | loss: 0.4871 | lr 2.7e-04")
    assert (i.epoch, i.step, i.loss, i.error, i.done) == (2, 400, 0.4871, None, False)


def test_val_loss_not_taken_as_train_loss():
    i = parse_line("Epoch 1/5 | val_loss: 0.5800 | auc 0.71")
    assert i.loss is None and i.error is None


def test_parse_variants():
    assert parse_line("{'loss': 0.25, 'learning_rate': 1e-05, 'epoch': 0.5}").loss == 0.25
    assert parse_line("iter 1200/5000 train_loss=1.23e-2").loss == 0.0123
    assert parse_line("iter 1200/5000 train_loss=1.23e-2").step == 1200
    assert parse_line("global_step=77 loss=3").step == 77
    assert parse_line("val_loss: nan").error


def test_normal_log_is_run():
    w, sent, _ = run_file("normal.log")
    assert sent[-1]["status"] == "run"
    assert sent[-1]["detail"] == "e2 s400 loss 0.4871"
    assert sent[-1]["key"] == "train:my-model"


def test_nan_is_error():
    w, sent, _ = run_file("nan.log")
    assert sent[-1]["status"] == "error"
    assert sent[-1]["detail"] == "NaN/inf loss s812"


def test_traceback_is_error_with_exception_line():
    w, sent, _ = run_file("crash.log")
    assert sent[-1]["status"] == "error"
    assert sent[-1]["detail"].startswith("RuntimeError: MPS backend out of memory")


def test_finished_is_done():
    w, sent, _ = run_file("finished.log")
    assert sent[-1]["status"] == "done"
    assert sent[-1]["detail"] == "done e5 s1500 loss 0.2187"


def test_jsonl_metrics():
    assert run_file("metrics.jsonl")[1][-1]["detail"] == "e1 s30 loss 0.987"
    assert run_file("metrics_nan.jsonl")[1][-1]["status"] == "error"
    assert run_file("metrics_done.jsonl")[1][-1]["status"] == "done"


def test_tqdm_carriage_returns():
    w, sent, _ = run_file("tqdm.log")
    assert sent[-1]["status"] == "run"
    assert math.isclose(w.state.loss, 0.433)


def test_stale_marks_done_after_n_minutes():
    w, sent, clock = run_file("normal.log", stale_minutes=5)
    clock[0] += 299
    w.check_stale()
    assert sent[-1]["status"] == "run"
    clock[0] += 2
    w.check_stale()
    assert sent[-1]["status"] == "done"
    assert sent[-1]["detail"].startswith("quiet 5m")


def test_stale_status_configurable():
    w, sent, clock = run_file("normal.log", stale_minutes=1, stale_status="needs")
    clock[0] += 61
    w.check_stale()
    assert sent[-1]["status"] == "needs"


def test_custom_done_pattern():
    w, sent, _ = run_file("normal.log", done_pattern=r"step 400")
    assert sent[-1]["status"] == "done"


def test_error_is_sticky():
    s = RunState()
    s.feed(parse_line("step 1 loss nan"), "x")
    s.feed(parse_line("step 2 loss 0.5"), "x")
    s.feed(parse_line("Training complete"), "x")
    assert s.status == "error"


def test_tail_real_file_with_truncation(tmp_path):
    p = tmp_path / "run.log"
    sent = []
    w = TrainWatcher(str(p), "r", sent.append)
    w.poll_once()                      # missing file: nothing yet
    assert sent == []
    p.write_text("step 1 loss 0.9\n")
    w.poll_once()
    assert sent[-1]["detail"] == "s1 loss 0.9"
    with p.open("a") as f:
        f.write("step 2 loss 0.8\nstep 3 lo")   # partial line kept for later
    w.poll_once()
    assert sent[-1]["detail"] == "s2 loss 0.8"
    with p.open("a") as f:
        f.write("ss 0.7\n")
    w.poll_once()
    assert sent[-1]["detail"] == "s3 loss 0.7"
    p.write_text("")                   # truncated: new run
    w.poll_once()
    p.write_text("step 9 loss 0.1\n")
    w.poll_once()
    w.poll_once()
    assert sent[-1]["detail"] == "s9 loss 0.1"
    w.stop()
