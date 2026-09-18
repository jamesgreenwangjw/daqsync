from __future__ import annotations

import argparse


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="daqsync", description="Align cam + MCU + boxes (mock by default).")
    p.add_argument("--seconds", type=float, default=1.0)
    p.add_argument("--out", default="run.csv")
    args = p.parse_args(argv)

    from daqsync import MockCamera, MockDetector, MockSerial, Session

    s = Session(MockCamera(fps=20), MockSerial(interval_s=0.01), MockDetector(infer_delay_s=0.02))
    table = s.run(seconds=args.seconds)
    table.to_csv(args.out)
    print(table.summary())
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
