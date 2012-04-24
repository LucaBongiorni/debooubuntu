from fabric.api import env
from fabric.api import local
from fabric.api import task
from fabric.api import lcd
from fabric.api import settings
from fabric.contrib.console import confirm
from fabric.contrib.files import append
from fabric.contrib.files import exists
from fabric.contrib.files import sed
from fabric.contrib.files import uncomment
from fabric.operations import prompt
from cuisine import dir_ensure

def err(msg):
        raise AttributeError(msg)

@task
def prepare(path=None, size=2000):
    """Prepares new ubuntu image"""
    opts= dict(
            size=size or env.get("size") or err("env.size must be set"),
            path=path or env.get('path') or err('env.path must be set')
            )

    print "Preparing in %(path)s" %opts
    with lcd(opts["path"]):
        local("dd if=/dev/zero of=root.img bs=1024k count=%(size)s" % opts)
        local("mkfs.ext4 -F -L root root.img")
        local("mkdir -p mnt")

@task
def mount(path=None):
    """Mounts image"""
    opts= dict(
            path=path or env.get("path") or err("env.path must be set")
            )

    with lcd(opts["path"]):
        local("sudo mount -o loop root.img mnt/")
        local("mkdir -p mnt/proc")
        local("sudo mount -t proc proc mnt/proc")
        local("mkdir -p mnt/dev")
        local("sudo mount --bind /dev mnt/dev")
        local("mkdir -p mnt/sys")
        local("sudo mount -t sysfs sysfs mnt/sys")

@task
def unmount(path=None):
    """Unmounts image"""

    opts= dict(
            path=path or env.get("path") or err("env.path must be set")
            )

    with lcd(opts["path"]):
        with settings(warn_only=True):
            local("sudo umount mnt/proc")
            local("sudo umount mnt/dev")
            local("sudo umount mnt/sys")
            local("sudo umount mnt/")

@task
def resize(path=None, size=2000):
    """Resizes an image"""

    opts= dict(
            path=path or env.get("path") or err("env.path must be set"),
            size=env.get("size") or size or err("env.size must be set")
            )

    with lcd(opts["path"]):
        with settings(warn_only=True):
            local("dd if=/dev/zero bs=1M count=%(size)s >> root.img" % opts)
            local("e2fsck -f root.img")
            local("resize2fs root.img")
            local("e2fsck -f root.img")

def chroot(command):
    local("sudo chroot mnt/ %s" % command)

def chins(packages, path="mnt"):
    local("sudo chroot %s apt-get install -y %s" % (path,packages,) )

@task
def install(path=None, 
        release="oneiric", mirror="http://de.archive.ubuntu.com/ubuntu/", target_arch="amd64",
        sources_list=None, network=None, dont_deboostrap=False):
    """Installs ubuntu to image"""

    opts= dict(
            path=path or env.get("path") or err("env.path must be set"),

            release=env.get("release") or release or err("env.release must be set"),
            mirror=env.get("mirror") or mirror or err("env.mirror must be set"),
            target_arch=env.get("target_arch") or target_arch or err("env.target_arch must be set"),

            sources_list=env.get("sources_list") or sources_list or None,
            network=env.get("network") or network or None,
            dont_deboostrap=env.get("dont_deboostrap") or dont_debootstrap or False
            )

    mount(path)

    with lcd(opts["path"]):
        if not opts["dont_deboostrap"]:
            local("sudo debootstrap --arch %(target_arch)s %(release)s mnt/ %(mirror)s" % opts)
    if opts["sources_list"]:
        local("sudo cp %(sources_list)s %(path)s" % opts)
    if opts["network"]:
        local("sudo cp %(network)s %(path)s" % opts)
    local("sudo cp /etc/mtab %(path)s/mnt/etc/mtab" % opts)

    with lcd(opts["path"]):
        print "Please enter new password"
        chroot("passwd")
        chroot("apt-get update")
        chins("openssh-server")
        chins("linux-image")

    unmount(path)

def post_flash():
    chroot("add user offlinehacker")
    chroot("usermod -a -G sudo offlinehacker")

@task
def flash(path=None, 
        root=None, swap=None, home=None):
    """Flashes ubuntu to drive"""
    opts= dict(
            path=path or env.get("path") or err("env.path must be set"),

            root=root or env.get("root") or err("env.root must be set"),
            swap=swap or env.get("swap") or err("env.swap must be set"),
            home=home or env.get("home") or None
            )

    mount(path)

    with lcd(opts["path"]):
        local("""echo \"UUID=$(sudo blkid -o value -s UUID %(root)s) / ext4 errors=remount-ro,user_xattr 0 1\" | sudo tee mnt/etc/fstab""" % opts)
        local("""echo \"UUID=$(sudo blkid -o value -s UUID %(swap)s) none    swap    sw      0 0\" | sudo tee -a mnt/etc/fstab""" % opts)
        if home:
            local("""echo \"UUID=$(sudo blkid -o value -s UUID %(home)s) /home   ext4 defaults   0 0\" | sudo tee -a mnt/etc/fstab""" % opts)

        local("sudo dd if=root.img of=%(root)s" % opts)

        local("mkdir -r flash/")
        local("sudo mount %(root)s flash/" % opts)
        local("sudo mkdir -p flash/proc")
        local("sudo mount -t proc proc flash/proc")
        local("sudo mkdir -p flash/dev")
        local("sudo mount --bind /dev flash/dev")
        local("sudo mkdir -p flash/sys")
        local("sudo mount -t sysfs sysfs flash/sys")

        chins("grub-pc")

        post_flash()

        local("sudo umount flash/sys")
        local("sudo umount flash/dev")
        local("sudo umount flash/proc")
        local("sudo umount flash")
        local("sudo rm -r flash")

    unmount(path)
    with lcd(opts["path"]):
        local("dd if=%(root) of=root.img" % opts)

@task
def create(path=None, 
        root=None, swap=None, home=None, 
        release="oneiric", mirror="http://de.archive.ubuntu.com/ubuntu/", target_arch="amd64",
        sources_list=None, network=None):
    """Creates ubuntu live usb"""

    opts= dict(
            path=path or env.get("path") or err("env.path must be set"),

            root=root or env.get("root") or err("env.root must be set"),
            swap=swap or env.get("swap") or err("env.swap must be set"),
            home=home or env.get("home") or None,

            release=env.get("release") or release or err("env.release must be set"),
            mirror=env.get("mirror") or mirror or err("env.mirror must be set"),
            target_arch=env.get("target_arch") or target_arch or err("env.target_arch must be set"),

            sources_list=env.get("sources_list") or sources_list or None,
            network=env.get("network") or network or None,
            )

    prepare(opts["path"])
    install(opts["path"], opts["release"], opts["mirror"], 
        opts["target_arch"], opts["sources_list"], opts["network"])
    flash(opts["path"], opts["root"], opts["swap"], opts["home"])
