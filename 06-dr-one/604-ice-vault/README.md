# 604-ice-vault

| | |
|---|---|
| **Category** | 06 — DR-ONE |
| **Points** | 245 |

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

Run the solver with the original challenge files in the paths expected by the source code.

```bash
gcc -O3 -fopenmp -Wno-deprecated-declarations 604_crack.c -o 604_crack -lcrypto
OMP_NUM_THREADS=6 ./604_crack mission_vault.7z
7z x mission_vault.7z -pqvfzk
cat ice_site.txt
```

Expected relevant output:

```text
7z: 506 bytes; encrypted header: 128 bytes; KDF rounds: 524288
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

The supplied source was uploaded as `604_crack(1).c`; save it as `604_crack.c` to use the command shown. The archive was successfully extracted with the recovered password. The survey text identifies the Utopia Planitia ice deposit at planetocentric coordinates 46.7 N, 97.3 E.

### Exploit Code

```c
#define _POSIX_C_SOURCE 200809L
#include <openssl/sha.h>
#include <openssl/evp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#include <time.h>
#include <omp.h>

#define TOTAL 11881376U
#define KDF_ROUNDS 524288U
#define HEADER_LENGTH 128U

static void fail(const char *message) { fprintf(stderr, "Error: %s\n", message); exit(1); }
static uint32_t read_u32(const unsigned char *p) { return (uint32_t)p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24); }
static uint64_t read_u64(const unsigned char *p) { uint64_t n=0; for(int i=7;i>=0;--i)n=(n<<8)|p[i]; return n; }
static uint64_t seven_uint(const unsigned char **pp, const unsigned char *end) {
    if(*pp>=end) fail("Truncated 7z varint");
    unsigned char first=*(*pp)++; unsigned char mask=0x80; uint64_t value=0;
    for(unsigned i=0;i<8;i++) {
        if(!(first&mask)) return value | ((uint64_t)(first & (mask-1)) << (8*i));
        if(*pp>=end) fail("Truncated 7z varint");
        value |= (uint64_t)*(*pp)++ << (8*i); mask >>= 1;
    }
    return value;
}
static void make_password(uint32_t n, char pass[6], unsigned char utf16[10]) {
    for(int i=4;i>=0;i--) { char c=(char)('a'+n%26U); n/=26U; pass[i]=c; utf16[i*2]=(unsigned char)c; utf16[i*2+1]=0; }
    pass[5]='\0';
}
static void key_7z(const unsigned char utf16[10], unsigned char key[32]) {
    SHA256_CTX ctx; unsigned char data[18]; memcpy(data,utf16,10); memset(data+10,0,8);
    SHA256_Init(&ctx);
    for(uint32_t i=0;i<KDF_ROUNDS;i++) {
        SHA256_Update(&ctx,data,sizeof(data));
        for(int j=10;j<18;j++) if(++data[j]!=0)break;
    }
    SHA256_Final(key,&ctx);
}
static int verify_archive(const char *archive, const char *password) {
    pid_t pid=fork(); if(pid<0)fail("fork failed");
    if(pid==0) {
        FILE *null=fopen("/dev/null","w"); if(null){dup2(fileno(null),STDOUT_FILENO);dup2(fileno(null),STDERR_FILENO);fclose(null);}
        char arg[8]; snprintf(arg,sizeof(arg),"-p%s",password);
        execlp("7z","7z","t","-y",arg,archive,(char *)NULL);
        _exit(127);
    }
    int status; if(waitpid(pid,&status,0)<0)fail("waitpid failed");
    return WIFEXITED(status)&&WEXITSTATUS(status)==0;
}
int main(int argc,char **argv) {
    if(argc<2 || argc>4) {fprintf(stderr,"Usage: %s mission_vault.7z [start_index] [max_candidates]\n",argv[0]);return 2;}
    const char *archive=argv[1]; FILE *fp=fopen(archive,"rb");if(!fp){perror("fopen");return 1;}
    if(fseek(fp,0,SEEK_END)!=0)fail("seek failed"); long file_size=ftell(fp);if(file_size<40)fail("7z too short"); rewind(fp);
    unsigned char *file=malloc((size_t)file_size);if(!file)fail("allocation failed");
    if(fread(file,1,(size_t)file_size,fp)!=(size_t)file_size)fail("read failed");fclose(fp);
    const unsigned char signature[6]={0x37,0x7a,0xbc,0xaf,0x27,0x1c};
    if(memcmp(file,signature,6)!=0)fail("Not 7z");
    uint64_t next_off=read_u64(file+12), next_size=read_u64(file+20);
    if(next_off+next_size > (uint64_t)file_size-32)fail("Invalid next header bounds");
    const unsigned char *h=file+32+next_off,*end=h+next_size,*p=h;
    if(p>=end || *p++!=0x17)fail("Expected encoded header (0x17)");
    if(p>=end || *p++!=0x06)fail("Expected PackInfo (0x06)");
    uint64_t packpos=seven_uint(&p,end), packcount=seven_uint(&p,end);
    if(packcount!=1 || p>=end || *p++!=0x09)fail("Expected one packed stream");
    uint64_t packsize=seven_uint(&p,end);
    if(packsize!=HEADER_LENGTH)fail("This program expects a 128-byte encrypted header");
    // Locate the AES coder signature in the encoded-header metadata.
    const unsigned char aes_codec[4]={0x06,0xf1,0x07,0x01};
    const unsigned char *codec=NULL;
    for(const unsigned char *q=h;q+4<=end;q++)if(memcmp(q,aes_codec,4)==0){codec=q;break;}
    if(!codec || codec+6>end)fail("7z AES metadata not found");
    unsigned char propsize=codec[4];
    if(propsize<2 || codec+5+propsize>end)fail("Invalid AES properties");
    const unsigned char *prop=codec+5;
    uint32_t power=prop[0]&0x3fU;
    uint32_t salt_len=((prop[0]>>7)&1U)+((prop[1]>>4)&0x0fU);
    uint32_t iv_len=((prop[0]>>6)&1U)+(prop[1]&0x0fU);
    if(power!=19U || salt_len!=0U || iv_len!=16U || propsize!=(unsigned char)(2+salt_len+iv_len))fail("Unexpected AES KDF metadata");
    unsigned char iv[16];memcpy(iv,prop+2,16);
    if(packpos+packsize > (uint64_t)file_size-32)fail("Invalid packed data bounds");
    const unsigned char *cipher=file+32+packpos;
    unsigned start=0,limit=TOTAL;
    if(argc>=3)start=(unsigned)strtoul(argv[2],NULL,10);
    if(argc>=4){unsigned count=(unsigned)strtoul(argv[3],NULL,10);limit=start+count;if(limit<start || limit>TOTAL)limit=TOTAL;}
    if(start>=TOTAL || start>=limit)fail("Invalid candidate range");
    fprintf(stderr,"7z: %ld bytes; encrypted header: %llu bytes; KDF rounds: %u; testing indices [%u,%u)\n",file_size,(unsigned long long)packsize,KDF_ROUNDS,start,limit);
    double begin=omp_get_wtime();
    unsigned long long completed=0;
    int found=0;
    char found_pass[6]={0};
    #pragma omp parallel
    {
        EVP_CIPHER_CTX *ctx=EVP_CIPHER_CTX_new();
        if(!ctx)fail("EVP allocation failed");
        #pragma omp for schedule(dynamic,32)
        for(unsigned n=start;n<limit;n++){
            if(__atomic_load_n(&found,__ATOMIC_RELAXED))continue;
            char pass[6];unsigned char wide[10],key[32],plain[16];
            make_password(n,pass,wide);
            key_7z(wide,key);
            int written=0;
            if(EVP_DecryptInit_ex(ctx,EVP_aes_256_cbc(),NULL,key,iv)!=1)fail("AES initialization failed");
            EVP_CIPHER_CTX_set_padding(ctx,0);
            if(EVP_DecryptUpdate(ctx,plain,&written,cipher,16)!=1 || written!=16)fail("AES decryption failed");
            if(plain[0]==0x01 && (plain[1]==0x02 || plain[1]==0x03 || plain[1]==0x04 || plain[1]==0x05)) {
                #pragma omp critical(verify)
                {
                    if(!found && verify_archive(archive,pass)){
                        strcpy(found_pass,pass);
                        __atomic_store_n(&found,1,__ATOMIC_RELAXED);
                    }
                }
            }
            unsigned long long progress=__atomic_add_fetch(&completed,1ULL,__ATOMIC_RELAXED);
            if(progress%4096ULL==0ULL){
                #pragma omp critical(progress)
                {
                    double elapsed=omp_get_wtime()-begin;
                    fprintf(stderr,"Progress %llu/%u (%.2f%%), %.1f candidates/s\n",
                        progress,limit-start,100.0*progress/(limit-start),progress/(elapsed>0?elapsed:1));
                }
            }
        }
        EVP_CIPHER_CTX_free(ctx);
    }
    if(found){printf("PASSWORD: %s\n",found_pass);free(file);return 0;}
    free(file);fprintf(stderr,"Password not found in the tested range.\n");return 1;
}
```

## Flag

```text
GAIANSPACE{UTOPIA_PLANITIA_46.7N_97.3E}
```
