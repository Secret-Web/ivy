def apply(hardware):
    for gpu in hardware.gpus:
        print(gpu.as_obj())

def revert(hardware):
    for gpu in hardware.gpus:
        print(gpu.as_obj())
