/*
 * kernel_example.c - Example kernel-style C code
 * Demonstrates various kernel patterns and constructs
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/spinlock.h>

#define MODULE_NAME "example"
#define MODULE_VERSION "1.0"
#define MAX_DEVICES 32

/* Module parameters */
static int debug_level = 0;
module_param(debug_level, int, 0644);
MODULE_PARM_DESC(debug_level, "Debug level (0-3)");

/* Global state */
static DEFINE_SPINLOCK(example_lock);
static struct list_head device_list;
static atomic_t device_count = ATOMIC_INIT(0);

/* Device structure */
struct example_device {
    char name[32];
    int id;
    struct list_head list;
    spinlock_t lock;
    void (*handler)(struct example_device *);
};

/* Function prototypes */
static int example_open(struct inode *inode, struct file *file);
static int example_release(struct inode *inode, struct file *file);
static ssize_t example_read(struct file *file, char __user *buf, size_t count, loff_t *ppos);
static ssize_t example_write(struct file *file, const char __user *buf, size_t count, loff_t *ppos);

/* File operations */
static const struct file_operations example_fops = {
    .owner = THIS_MODULE,
    .open = example_open,
    .release = example_release,
    .read = example_read,
    .write = example_write,
};

/* Macro for debug printing */
#define DEBUG_PRINT(level, fmt, args...) \
    do { \
        if (debug_level >= (level)) \
            printk(KERN_DEBUG MODULE_NAME ": " fmt "\n", ##args); \
    } while (0)

/* Static inline helper function */
static inline int is_device_valid(struct example_device *dev)
{
    return dev && dev->id >= 0 && dev->id < MAX_DEVICES;
}

/* Device initialization */
static int init_device(struct example_device *dev, int id)
{
    if (!dev)
        return -EINVAL;
    
    memset(dev, 0, sizeof(*dev));
    dev->id = id;
    snprintf(dev->name, sizeof(dev->name), "device%d", id);
    spin_lock_init(&dev->lock);
    INIT_LIST_HEAD(&dev->list);
    
    DEBUG_PRINT(1, "Initialized device %s", dev->name);
    return 0;
}

/* File operation implementations */
static int example_open(struct inode *inode, struct file *file)
{
    DEBUG_PRINT(2, "Device opened");
    return 0;
}

static int example_release(struct inode *inode, struct file *file)
{
    DEBUG_PRINT(2, "Device released");
    return 0;
}

static ssize_t example_read(struct file *file, char __user *buf, size_t count, loff_t *ppos)
{
    return -ENOSYS;  // Not implemented
}

static ssize_t example_write(struct file *file, const char __user *buf, size_t count, loff_t *ppos)
{
    return -ENOSYS;  // Not implemented
}

/* Module initialization */
static int __init example_init(void)
{
    int ret;
    
    printk(KERN_INFO MODULE_NAME ": Loading module version " MODULE_VERSION "\n");
    
    INIT_LIST_HEAD(&device_list);
    
    /* Register character device */
    ret = register_chrdev(0, MODULE_NAME, &example_fops);
    if (ret < 0) {
        printk(KERN_ERR MODULE_NAME ": Failed to register device\n");
        return ret;
    }
    
    DEBUG_PRINT(0, "Module initialized successfully");
    return 0;
}

/* Module cleanup */
static void __exit example_exit(void)
{
    struct example_device *dev, *tmp;
    
    printk(KERN_INFO MODULE_NAME ": Unloading module\n");
    
    /* Clean up devices */
    spin_lock(&example_lock);
    list_for_each_entry_safe(dev, tmp, &device_list, list) {
        list_del(&dev->list);
        kfree(dev);
    }
    spin_unlock(&example_lock);
    
    unregister_chrdev(0, MODULE_NAME);
}

module_init(example_init);
module_exit(example_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Example Author");
MODULE_DESCRIPTION("Example kernel module demonstrating various patterns");
MODULE_VERSION(MODULE_VERSION);