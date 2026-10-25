# Integrity and authorization

The complete `checksums.sha256` inventory covers every Pack payload file except the inventory itself. Slurm loads it using a host-approved inventory digest. ZIP sidecars protect archive integrity; checksum verification alone does not establish publisher identity. GitHub source revision and bundle identity are recorded separately. Loading a verified Pack does not grant filesystem, network, SSH or vault access.
