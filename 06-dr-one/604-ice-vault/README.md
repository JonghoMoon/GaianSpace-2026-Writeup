# 604-ice-vault

| | |
|---|---|
| **Category** | 06 — DR-ONE |
| **Points** | 125 |

## Description

This is what the whole flight was for. DR-ONE's survey confirmed a buried target, and the mission team sealed the coordinates in a vault before relaying anything home — no site location was ever sent in the clear. We pulled the sealed vault off the relay. The only thing standing between us and the find is the lock the field team threw on it in a hurry: a short, sloppy maintenance passphrase, five lowercase letters and not a real word, the kind of thing they rotate every sortie and never write down.

Short and sloppy still means work. There is no word to guess and no hint to shortcut — the passphrase has to be ground out, every combination, until the vault opens. A desktop left running will get there in a few hours. What is inside is the thing everyone has been after: where the ice is.

Open the vault and read the find.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `mission_vault.7z` — the sealed survey vault
- `vault_notes.md` — what the field team said about the lock

## Solution

### Steps

1. Confirm the archive uses encrypted 7z headers. The usual `7z2john` and `7z2hashcat` tools produced empty output because the encrypted header lacks a usable digest for their extraction path.
2. Read the encoded 7z header and locate the AES coder metadata, salt, IV, and iteration count (`2^19 = 524288` SHA-256 rounds).
3. Enumerate all `26^5 = 11,881,376` five-letter lowercase passwords with OpenMP and OpenSSL.
4. Derive each candidate key using the 7z SHA-256 KDF and decrypt the first AES-CBC header block. Use the expected header prefix as a cheap filter.
5. Confirm candidate passwords with `7z t`; the recovered password is `qvfzk`.
6. Extract the archive and inspect the enclosed survey text. The exact final flag must be copied from that file, not inferred from the password.

### Reproduction

The Linux solver requires a C compiler, OpenMP, OpenSSL development headers/libraries, and the `7z` command. The original search used both a Linux VM and a Windows host.

Run the solver with the original challenge files in the paths expected by the source code.

The password was recovered by an **exhaustive-search attempt split across two computers**. The author started the search at index `0` on a Linux virtual machine, while a Windows-host executable searched from an intermediate index toward the end of the same five-letter lowercase keyspace. **The Windows process found the password.** This was not a search limited to the already-known winning index, and no smaller predetermined candidate set was used to discover the password.

The precise split index and Windows build command were not preserved in this archive, so they should not be presented as exact historical commands. The search space contains `26^5 = 11,881,376` candidates, with indices `0` through `11,881,375`. The solver supports a starting index and a maximum number of candidates, enabling the same split to be reproduced without overlapping search ranges. For example, to split the keyspace at index `6,000,000` (an **illustrative split, not a claim about the original run**):

**Linux VM — indices 0 to 5,999,999:**

```bash
sudo apt update
sudo apt install -y build-essential libssl-dev libomp-dev p7zip-full
gcc -O3 -fopenmp -Wno-deprecated-declarations 604_crack.c -o 604_crack -lcrypto
OMP_NUM_THREADS=12 ./604_crack mission_vault.7z 0 6000000
```

**Windows host — indices 6,000,000 to 11,881,375:**

Run the Windows build of `604_crack_win.c` from PowerShell with OpenSSL, OpenMP, and `7z` available:

```powershell
.\604_crack_win.exe mission_vault.7z 6000000 5881376
```

The example partitions are disjoint and together cover all 11,881,376 candidates. Each instance stops when it finds and successfully verifies a password; the other instance can then be stopped manually. Compile the Windows executable with a toolchain supporting OpenMP and OpenSSL, or use the executable already built for the original search.

**Measured throughput on a dual-socket workstation (additional validation):**

A later Linux run on an HP Z8 workstation with **two Intel Xeon Silver 4510 CPUs** (24 physical cores and 48 logical processors in total) measured the search rate at two OpenMP thread counts. These measurements are separate from the original split Linux-VM/Windows-host search, in which the **Windows executable recovered the password**.

```bash
OMP_NUM_THREADS=36 ./604_crack mission_vault.7z
OMP_NUM_THREADS=48 ./604_crack mission_vault.7z
```

Selected progress messages from the two runs:

```text
# 36-thread run
Progress 757760/11881376 (6.38%), 3102.0 candidates/s

# 48-thread run
Progress 40960/11881376 (0.34%), 3748.1 candidates/s
```

| Threads | Observed rate | Estimated time for all 11,881,376 candidates |
|---:|---:|---:|
| 36 | 3,102.0 candidates/s | Approximately 1 h 3 min 50 s |
| 48 | 3,748.1 candidates/s | Approximately 52 min 50 s |

The estimates use `total_candidates / observed_candidates_per_second`, assuming a constant rate and no early match. At the sampled progress points, **48 threads were approximately 20.8% faster** than 36 threads, implying roughly **11 minutes less** for an uninterrupted full-keyspace pass. These are observed *cumulative rates at different points in separate runs*, not final steady-state benchmarks; sustained throughput, CPU frequency, and the exact password discovery time can vary. An exhaustive search can terminate early when a match is verified.

**Quick verification after password recovery (not the original exhaustive search):**

```bash
OMP_NUM_THREADS=12 ./604_crack mission_vault.7z 7684700 100
7z x mission_vault.7z -pqvfzk
cat ice_site.txt
```

The short range includes the discovered password `qvfzk` at index `7,684,752`. It is provided only to make verification fast; it must not be mistaken for the search that discovered the password.

Expected relevant output from the **short verification run**:

```text
7z: 506 bytes; encrypted header: 128 bytes; KDF rounds: 524288; testing indices [7684700,7684800)
PASSWORD: qvfzk
...
Testing archive: mission_vault.7z
Everything is Ok
PASSWORD: qvfzk

Extracting archive: mission_vault.7z
Everything is Ok
Size:       405
Compressed: 506

DR-ONE subsurface survey — CONFIDENTIAL mission vault
=====================================================

Primary subsurface water-ice target confirmed by SHARAD-class sounding
and the onboard perception stack over multiple passes.

Deposit: Utopia Planitia mid-latitude ice sheet (volume ~ a small sea).
Survey marker (planetocentric): 46.7 N, 97.3 E.

FLAG: GAIANSPACE{UTOPIA_PLANITIA_46.7N_97.3E}
```

The supplied source `604_crack.c` implements the search ranges shown above. The archive was extracted with the recovered password during the original solve; the displayed extraction log is retained as evidence from that run. The survey text identifies the Utopia Planitia ice deposit at planetocentric coordinates 46.7 N, 97.3 E.

### Solver Code

```c
/*
 * Dependencies (Ubuntu/Debian):
 *   sudo apt update
 *   sudo apt install -y build-essential libssl-dev libomp-dev p7zip-full
 * Build on Linux:
 *   gcc -O3 -fopenmp -Wno-deprecated-declarations 604_crack.c -o 604_crack -lcrypto
 * Windows: compile with a Windows OpenMP/OpenSSL-enabled C toolchain and
 *   provide the 7z executable in PATH. Compilation details depend on the toolchain.
 */

/*
 * 604_crack.c
 *
 * Recover a five-letter lowercase password from a 7z archive whose
 * encrypted header uses AES-256-CBC and a SHA-256 KDF.
 *
 * This solver is tailored to the challenge archive:
 *   - Passwords: five lowercase ASCII letters (26^5 candidates)
 *   - KDF: SHA-256, 2^19 rounds, no salt
 *   - AES: 256-bit CBC with a 16-byte IV
 *   - Encrypted header: 128 bytes
 *
 * Candidate testing:
 *   1. Derive the candidate key.
 *   2. Decrypt the first 16 bytes of the encoded header.
 *   3. Check the expected header prefix.
 *   4. Verify promising candidates with 7-Zip.
 *
 * The program stops checking new candidates once a password is found.
 * Some already-running OpenMP iterations may finish before all threads exit.
 */

#include <openssl/evp.h>
#include <openssl/sha.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <omp.h>

#ifdef _WIN32
#include <process.h>
#else
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

#define PASSWORD_LENGTH       5U
#define PASSWORD_COUNT        11881376U
#define KDF_ROUNDS            524288U
#define ENCRYPTED_HEADER_SIZE 128U
#define AES_BLOCK_SIZE        16U
#define PROGRESS_INTERVAL     4096ULL

typedef struct {
    unsigned char *data;
    size_t size;
    const unsigned char *encrypted_header;
    unsigned char iv[AES_BLOCK_SIZE];
} ArchiveInfo;

typedef struct {
    uint32_t begin;
    uint32_t end;
} SearchRange;

static void fatal(const char *message)
{
    fprintf(stderr, "Error: %s\n", message);
    exit(EXIT_FAILURE);
}

static uint64_t read_le64(const unsigned char *data)
{
    uint64_t value = 0U;

    for (int index = 7; index >= 0; --index) {
        value = (value << 8) | (uint64_t)data[index];
    }

    return value;
}

/* Decode a variable-length unsigned integer from a 7z header. */
static uint64_t read_7z_uint(
    const unsigned char **cursor,
    const unsigned char *end)
{
    if (*cursor >= end) {
        fatal("Truncated 7z integer");
    }

    const unsigned char first = *(*cursor)++;
    unsigned char mask = 0x80U;
    uint64_t value = 0U;

    for (unsigned int index = 0U; index < 8U; ++index) {
        if ((first & mask) == 0U) {
            return value |
                ((uint64_t)(first & (unsigned char)(mask - 1U)) << (8U * index));
        }

        if (*cursor >= end) {
            fatal("Truncated 7z integer");
        }

        value |= (uint64_t)*(*cursor)++ << (8U * index);
        mask >>= 1U;
    }

    return value;
}

static unsigned char *read_entire_file(
    const char *path,
    size_t *file_size)
{
    FILE *file = fopen(path, "rb");
    if (file == NULL) {
        perror(path);
        exit(EXIT_FAILURE);
    }

    if (fseek(file, 0L, SEEK_END) != 0) {
        fatal("Unable to seek archive");
    }

    const long length = ftell(file);
    if (length < 40L) {
        fatal("Archive is too short");
    }

    if (fseek(file, 0L, SEEK_SET) != 0) {
        fatal("Unable to rewind archive");
    }

    *file_size = (size_t)length;
    unsigned char *data = (unsigned char *)malloc(*file_size);
    if (data == NULL) {
        fatal("Unable to allocate archive buffer");
    }

    if (fread(data, 1U, *file_size, file) != *file_size) {
        fatal("Unable to read archive");
    }

    fclose(file);
    return data;
}

/* Locate the encoded 7z header and extract its AES IV. */
static ArchiveInfo load_archive(const char *path)
{
    static const unsigned char signature[6] = {
        0x37U, 0x7AU, 0xBCU, 0xAFU, 0x27U, 0x1CU
    };
    static const unsigned char aes_codec[4] = {
        0x06U, 0xF1U, 0x07U, 0x01U
    };

    ArchiveInfo archive = {0};
    archive.data = read_entire_file(path, &archive.size);

    if (memcmp(archive.data, signature, sizeof(signature)) != 0) {
        fatal("Input is not a 7z archive");
    }

    const uint64_t next_offset = read_le64(archive.data + 12U);
    const uint64_t next_size = read_le64(archive.data + 20U);
    const uint64_t body_size = (uint64_t)archive.size - 32U;

    if (next_offset > body_size ||
        next_size > body_size - next_offset) {
        fatal("Invalid encoded-header bounds");
    }

    const unsigned char *header =
        archive.data + 32U + (size_t)next_offset;
    const unsigned char *end = header + (size_t)next_size;
    const unsigned char *cursor = header;

    if (cursor >= end || *cursor++ != 0x17U) {
        fatal("Expected encoded header (0x17)");
    }
    if (cursor >= end || *cursor++ != 0x06U) {
        fatal("Expected PackInfo (0x06)");
    }

    const uint64_t pack_offset = read_7z_uint(&cursor, end);
    const uint64_t pack_count = read_7z_uint(&cursor, end);

    if (pack_count != 1U || cursor >= end || *cursor++ != 0x09U) {
        fatal("Expected exactly one packed stream");
    }

    const uint64_t pack_size = read_7z_uint(&cursor, end);
    if (pack_size != ENCRYPTED_HEADER_SIZE) {
        fatal("Expected a 128-byte encrypted header");
    }

    const unsigned char *codec = NULL;
    for (const unsigned char *p = header; p + 4U <= end; ++p) {
        if (memcmp(p, aes_codec, sizeof(aes_codec)) == 0) {
            codec = p;
            break;
        }
    }

    if (codec == NULL || (size_t)(end - codec) < 6U) {
        fatal("AES coder metadata not found");
    }

    const unsigned int property_size = (unsigned int)codec[4];
    if ((size_t)(end - (codec + 5U)) < property_size ||
        property_size < 2U) {
        fatal("Invalid AES properties");
    }

    const unsigned char *properties = codec + 5U;
    const unsigned int rounds_power = (unsigned int)(properties[0] & 0x3FU);
    const unsigned int salt_size =
        (unsigned int)((properties[0] >> 7U) & 1U) +
        (unsigned int)((properties[1] >> 4U) & 0x0FU);
    const unsigned int iv_size =
        (unsigned int)((properties[0] >> 6U) & 1U) +
        (unsigned int)(properties[1] & 0x0FU);

    if (rounds_power != 19U ||
        salt_size != 0U ||
        iv_size != AES_BLOCK_SIZE ||
        property_size != 2U + salt_size + iv_size) {
        fatal("Unexpected AES/KDF configuration");
    }

    memcpy(archive.iv, properties + 2U, AES_BLOCK_SIZE);

    if (pack_offset > body_size ||
        pack_size > body_size - pack_offset) {
        fatal("Invalid encrypted-header bounds");
    }

    archive.encrypted_header =
        archive.data + 32U + (size_t)pack_offset;

    return archive;
}

/* Convert a candidate index to a password and UTF-16LE bytes. */
static void index_to_password(
    uint32_t index,
    char password[PASSWORD_LENGTH + 1U],
    unsigned char utf16[PASSWORD_LENGTH * 2U])
{
    for (int position = (int)PASSWORD_LENGTH - 1; position >= 0; --position) {
        const unsigned char letter =
            (unsigned char)('a' + (int)(index % 26U));

        index /= 26U;
        password[position] = (char)letter;
        utf16[(size_t)position * 2U] = letter;
        utf16[(size_t)position * 2U + 1U] = 0U;
    }

    password[PASSWORD_LENGTH] = '\0';
}

/* Derive the 7z AES key using SHA-256 over password and round counter. */
static void derive_key(
    const unsigned char utf16[PASSWORD_LENGTH * 2U],
    unsigned char key[SHA256_DIGEST_LENGTH])
{
    unsigned char input[PASSWORD_LENGTH * 2U + 8U] = {0};
    SHA256_CTX hash;

    memcpy(input, utf16, PASSWORD_LENGTH * 2U);

    if (SHA256_Init(&hash) != 1) {
        fatal("SHA-256 initialization failed");
    }

    for (uint32_t round = 0U; round < KDF_ROUNDS; ++round) {
        if (SHA256_Update(&hash, input, sizeof(input)) != 1) {
            fatal("SHA-256 update failed");
        }

        /* Increment the 64-bit little-endian round counter. */
        for (size_t index = PASSWORD_LENGTH * 2U;
             index < sizeof(input); ++index) {
            input[index] = (unsigned char)(input[index] + 1U);
            if (input[index] != 0U) {
                break;
            }
        }
    }

    if (SHA256_Final(key, &hash) != 1) {
        fatal("SHA-256 finalization failed");
    }
}

/* Quickly reject keys whose decrypted header has the wrong prefix. */
static int header_looks_valid(
    EVP_CIPHER_CTX *context,
    const ArchiveInfo *archive,
    const unsigned char key[SHA256_DIGEST_LENGTH])
{
    unsigned char plaintext[AES_BLOCK_SIZE];
    int written = 0;

    if (EVP_DecryptInit_ex(
            context, EVP_aes_256_cbc(), NULL, key, archive->iv) != 1) {
        fatal("AES initialization failed");
    }

    if (EVP_CIPHER_CTX_set_padding(context, 0) != 1) {
        fatal("Unable to disable AES padding");
    }

    if (EVP_DecryptUpdate(
            context, plaintext, &written,
            archive->encrypted_header, AES_BLOCK_SIZE) != 1 ||
        written != (int)AES_BLOCK_SIZE) {
        fatal("AES decryption failed");
    }

    return plaintext[0] == 0x01U &&
           plaintext[1] >= 0x02U &&
           plaintext[1] <= 0x05U;
}

/* Test a promising password using the installed 7z command. */
static int verify_with_7zip(const char *path, const char *password)
{
    char password_option[3U + PASSWORD_LENGTH] = {0};
    snprintf(password_option, sizeof(password_option), "-p%s", password);

#ifdef _WIN32
    const char *arguments[] = {
        "7z", "t", "-y", password_option, path, NULL
    };
    const intptr_t status = _spawnvp(_P_WAIT, "7z", arguments);
    return status == 0;
#else
    const pid_t child = fork();
    if (child < 0) {
        fatal("Unable to create 7z verification process");
    }

    if (child == 0) {
        FILE *sink = fopen("/dev/null", "w");
        if (sink != NULL) {
            (void)dup2(fileno(sink), STDOUT_FILENO);
            (void)dup2(fileno(sink), STDERR_FILENO);
            fclose(sink);
        }

        execlp("7z", "7z", "t", "-y", password_option, path, (char *)NULL);
        _exit(127);
    }

    int status = 0;
    if (waitpid(child, &status, 0) < 0) {
        fatal("Unable to wait for 7z verification");
    }

    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
#endif
}

static uint32_t parse_index(const char *text)
{
    char *end = NULL;
    const unsigned long value = strtoul(text, &end, 10);

    if (text[0] == '\0' || end == text || *end != '\0' ||
        value > PASSWORD_COUNT) {
        fatal("Invalid candidate index or count");
    }

    return (uint32_t)value;
}

static SearchRange parse_range(int argc, char **argv)
{
    SearchRange range = {0U, PASSWORD_COUNT};

    if (argc >= 3) {
        range.begin = parse_index(argv[2]);
    }

    if (argc >= 4) {
        const uint32_t count = parse_index(argv[3]);
        const uint32_t remaining = PASSWORD_COUNT - range.begin;
        range.end = range.begin + (count < remaining ? count : remaining);
    }

    if (range.begin >= PASSWORD_COUNT || range.begin >= range.end) {
        fatal("Empty or invalid candidate range");
    }

    return range;
}

static int search_password(
    const ArchiveInfo *archive,
    const char *archive_path,
    SearchRange range,
    char result[PASSWORD_LENGTH + 1U])
{
    int found = 0;
    unsigned long long completed = 0ULL;
    const double started = omp_get_wtime();

    #pragma omp parallel
    {
        EVP_CIPHER_CTX *context = EVP_CIPHER_CTX_new();
        if (context == NULL) {
            fatal("Unable to allocate AES context");
        }

        #pragma omp for schedule(dynamic, 32)
        for (uint32_t index = range.begin; index < range.end; ++index) {
            int already_found = 0;

            #pragma omp atomic read
            already_found = found;

            if (already_found != 0) {
                continue;
            }

            char password[PASSWORD_LENGTH + 1U];
            unsigned char utf16[PASSWORD_LENGTH * 2U];
            unsigned char key[SHA256_DIGEST_LENGTH];

            index_to_password(index, password, utf16);
            derive_key(utf16, key);

            if (header_looks_valid(context, archive, key)) {
                #pragma omp critical(verify)
                {
                    if (found == 0 &&
                        verify_with_7zip(archive_path, password)) {
                        memcpy(result, password, PASSWORD_LENGTH + 1U);

                        #pragma omp atomic write
                        found = 1;
                    }
                }
            }

            unsigned long long progress = 0ULL;

            #pragma omp atomic capture
            progress = ++completed;

            if (progress % PROGRESS_INTERVAL == 0ULL) {
                #pragma omp critical(progress_output)
                {
                    const double elapsed = omp_get_wtime() - started;
                    const double rate =
                        (double)progress / (elapsed > 0.0 ? elapsed : 1.0);
                    const double percentage =
                        100.0 * (double)progress /
                        (double)(range.end - range.begin);

                    fprintf(stderr,
                        "Progress %llu/%u (%.2f%%), %.1f candidates/s\n",
                        progress, range.end - range.begin, percentage, rate);
                }
            }
        }

        EVP_CIPHER_CTX_free(context);
    }

    return found;
}

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 4) {
        fprintf(stderr,
            "Usage: %s mission_vault.7z [start_index] [max_candidates]\n",
            argv[0]);
        return EXIT_FAILURE;
    }

    const char *archive_path = argv[1];
    const SearchRange range = parse_range(argc, argv);
    ArchiveInfo archive = load_archive(archive_path);

    fprintf(stderr,
        "7z: %zu bytes; encrypted header: %u bytes; "
        "KDF rounds: %u; testing indices [%u,%u)\n",
        archive.size, ENCRYPTED_HEADER_SIZE, KDF_ROUNDS,
        range.begin, range.end);

    char password[PASSWORD_LENGTH + 1U] = {0};
    const int found = search_password(
        &archive, archive_path, range, password);

    free(archive.data);

    if (found != 0) {
        printf("PASSWORD: %s\n", password);
        return EXIT_SUCCESS;
    }

    fprintf(stderr, "Password not found in the tested range.\n");
    return EXIT_FAILURE;
}
```

## Flag

```text
GAIANSPACE{UTOPIA_PLANITIA_46.7N_97.3E}
```
