# C12 Image-lab Kernel Config Policy

C12.1.11 keeps Armbian `overlayroot`, but stops the failed line of loading
`overlay.ko` as a module from initramfs.

The next image-lab build must provide a complete Armbian kernel config userpatch:

- name: `linux-sunxi64-current.config`
- source: Armbian Build `config/kernel/linux-sunxi64-current.config`
- required change: `CONFIG_OVERLAY_FS=y`

The build runner creates the full userpatch file outside this repository under
Armbian Build's `userpatches/` directory when invoked with:

```text
C12_KERNEL_OVERLAYFS_BUILTIN=1
```

Do not commit a partial Kconfig fragment. Armbian Build expects the complete
kernel config for this path.
