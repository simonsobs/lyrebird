"""Tool to extract a particular configuration from a hardware file"""
import toml
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("hardware_file", help="Path to hardware toml file")
parser.add_argument("wafer_slot", help="Wafer slot id to extract")
parser.add_argument("--output", "-o", help="Output file")

args = parser.parse_args()

hardware = toml.load(args.hardware_file)
dets = {
    k: v for k, v in hardware['detectors'].items()
    if v['wafer_slot'] == args.wafer_slot
}
if args.output is not None:
    fname = args.output
else:
    fname = f'{args.wafer_slot}_dets.toml'
with open(fname, 'w') as f:
    toml.dump(dets, f)
