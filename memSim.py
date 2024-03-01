#!/usr/bin/python3

import sys
from collections import deque
from enum import Enum

# Constants
PAGE_SIZE = 256
BACKING_STORE_FILE = "BACKING_STORE.bin"
#ADDRESS_FILE = sys.argv[1]

# enum for Page Replacement Algorithms
class page_replacement_alg(Enum):
    FIFO = 1
    LRU = 2
    OPT = 3

def lru(page_lru_counter, page_number, page_table):
    if not page_lru_counter:
        return -1  # or handle the case when the list is empty

    # find the least recently used page
    least_recently_used_page = None
    min_use_index = float('inf')
    for i, use_index in enumerate(page_lru_counter):
        if use_index is not None and use_index < min_use_index:
            min_use_index = use_index
            least_recently_used_page = i

    frame_number = least_recently_used_page
    page_lru_counter[frame_number] = page_number

    # update page table for the evicted page
    if page_table[frame_number]["loaded"]:
        page_table[frame_number]["loaded"] = False

    # update page table for the new page
    page_table[page_number]["frame_number"] = frame_number
    page_table[page_number]["loaded"] = True

    return frame_number

def fifo(page_queue, page_number, frames, page_table):
    if len(page_queue) < frames:
        frame_number = len(page_queue)
        page_queue.append(frame_number)
    else:
        frame_number = page_queue.popleft()
        page_queue.append(frame_number)
        # update page table for the evicted page
        page_table[frame_number]["loaded"] = False
    return frame_number

def opt(page_opt_counter, page_opt_references, page_table):
    # find the page that will not be used for the longest time in the future
    farthest = -1
    victim_page = None
    for page_number, references in enumerate(page_opt_references):
        if not references:
            return page_number  # if a page is never referenced in future, return it immediately
        if references[0] > farthest:
            farthest = references[0]
            victim_page = page_number

    # update page table for the evicted page
    if victim_page is not None and page_table[victim_page]["loaded"]:
        page_table[victim_page]["loaded"] = False

    return victim_page

def load_page_from_backing_store(page_number):
    try:
        with open(BACKING_STORE_FILE, "rb") as backing_store:
            backing_store.seek(page_number * PAGE_SIZE)
            return backing_store.read(PAGE_SIZE)
    except IOError as e:
        print("Error loading page from backing store", e)
        return None

def convert_physical_address(frame_number, offset):
    return frame_number * PAGE_SIZE + offset

def main():
    # set default values
    FRAMES = 256
    PRA = "FIFO"

    # parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python3 program.py <reference-sequence-file.txt> [<FRAMES> <PRA>]")
        return
    ADDRESS_FILE = sys.argv[1]
    if (len(sys.argv) >= 3):
        arg = sys.argv[2]
        if arg.isdigit():
            FRAMES = int(arg)
            if (FRAMES < 0 or FRAMES > 256):
                print("FRAMES must be between 0 and 256")
                return
        else:
            PRA = arg.upper()
    if (len(sys.argv) >= 4):
        PRA = sys.argv[3].upper()

    PHYSICAL_MEMORY_SIZE = 256 * FRAMES


    # initialize physical memory and other data structures
    physical_memory = [None] * PHYSICAL_MEMORY_SIZE
    tlb = []
    page_table = [{"frame_number": -1, "loaded": False} for _ in range(256)]

    # initialize page queue for FIFO
    page_queue = deque(maxlen=FRAMES)

    # init page replacement algorithm
    if PRA == "FIFO":
        page_replacement_algorithm = page_replacement_alg.FIFO
    elif PRA == "LRU":
        page_replacement_algorithm = page_replacement_alg.LRU
    elif PRA == "OPT":
        page_replacement_algorithm = page_replacement_alg.OPT
        page_opt_counter = [0] * FRAMES
        page_opt_references = [[] for _ in range(256)]
        with open(ADDRESS_FILE, "r") as address_file:
            for i, line in enumerate(address_file):
                logical_address = int(line.strip())
                page_number = (logical_address >> 8) & 0xFF
                page_opt_references[page_number].append(i)
    else:
        print("Invalid page replacement algorithm. Choose from 'fifo', 'lru', or 'opt'.")
        return

    # init counters
    page_faults = 0
    tlb_hits = 0
    tlb_misses = 0
    total_addresses = 0

    # specific for lru/opt
    page_lru_counter = {}
    page_opt_counter = []

    # process addresses
    with open(ADDRESS_FILE, "r") as address_file:
        for line in address_file:
            total_addresses += 1

            logical_address = int(line.strip())
            # mask 16 rightmost bits / divide
            page_number = (logical_address >> 8) & 0xFF
            offset = logical_address & 0xFF

            # TLB lookup
            tlb_hit = False
            for entry in tlb:
                if entry["page_number"] == page_number:
                    tlb_hit = True
                    frame_number = entry["frame_number"]
                    break

            if tlb_hit:
                print(f"HIT on address {logical_address} on frame {frame_number}")
                tlb_hits += 1
            else:
                tlb_misses += 1
                print(f"MISS on address {logical_address}")

                # page table lookup
                frame_number = -1
                for entry in page_table:
                    if entry["frame_number"] == page_number:
                        print("nOT USELESS")
                        frame_number = entry["frame_number"]
                        if not entry["loaded"]:
                            page_faults += 1
                        break

                if frame_number == -1:
                    # page fault or soft miss
                    page_faults += 1

                    # find a free frame or use page replacement algorithm
                    if len(page_queue) < FRAMES:
                        frame_number = len(page_queue)
                        page_queue.append(frame_number)
                    elif page_replacement_algorithm == page_replacement_alg.FIFO:
                        frame_number = fifo(page_queue, page_number, FRAMES, page_table)
                    elif page_replacement_algorithm == page_replacement_alg.LRU:
                        frame_number = lru(page_lru_counter, page_number, page_table)
                    elif page_replacement_algorithm == page_replacement_alg.OPT:
                        frame_number = opt(page_opt_counter, page_opt_references, page_table)

                    # load page from backing store after its viable
                    page_data = load_page_from_backing_store(page_number)
                    # update physical memory
                    physical_memory[frame_number * PAGE_SIZE:(frame_number + 1) * PAGE_SIZE] = page_data
                    page_table[page_number]["frame_number"] = frame_number
                    page_table[page_number]["loaded"] = True

                    # update TLB
                    tlb_entry = {"page_number": page_number, "frame_number": frame_number}
                    tlb.append(tlb_entry)
                    if len(tlb) > 16:
                        tlb.pop(0)

            # calculate physical address and retrieve value
            physical_address = convert_physical_address(frame_number, offset)
            value = physical_memory[physical_address]

            # print output using proper byte format
            frame_content = "".join("{:02x}".format(byte) for byte in physical_memory[frame_number * PAGE_SIZE:(frame_number + 1) * PAGE_SIZE])
            #print(f"{logical_address},{value},{frame_number},{frame_content}")
            #print(f"{logical_address},{value},{frame_number}")

    # calculate statistics
    page_fault_rate = page_faults / total_addresses * 100 if total_addresses > 0 else 0
    tlb_miss_rate = tlb_misses / total_addresses * 100 if total_addresses > 0 else 0

    # print statistics
    print(f"Page Faults: {page_faults}, Page Fault Rate: {page_fault_rate}%")
    print(f"TLB Hits: {tlb_hits}, TLB Misses: {tlb_misses}")

if __name__ == "__main__":
    main()