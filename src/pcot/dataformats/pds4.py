from pathlib import Path
from proctools.products.loader import ProductLoader


def read_all(dir_):
    loader = ProductLoader()
    num_loaded = loader.load_products(dir_, recursive=True)
    print(f"found {num_loaded} products")
    # Retrieve all loaded PAN-PP-220/spec-rad products as instances of
    # proctools.products.pancam:SpecRad; sub in the mnemonic of the product you're after

    for product in loader.all("spec-rad"):
        # DataProduct.meta provides convenient access to common label attributes.
        # See proctools.products.pancam.__init__ for the currently defined mappings
        m = product.meta
        print(
            f"type={m.acq_id}, cam={m.camera}, sol={m.sol_id}, seq={m.seq_num},"
            f" rmc_ptu={m.rmc_ptu}, cwl={m.filter_cwl}, filt={m.filter_id}"
        )

# read_all(Path("z:/rcp_output"))
