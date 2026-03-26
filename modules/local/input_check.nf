// Input validation and samplesheet generation

process INPUT_CHECK {
    tag "input_check"

    input:
    path(reads)

    output:
    path("samplesheet.csv"), emit: samplesheet

    script:
    """
    echo "sample,fastq_1,fastq_2" > samplesheet.csv
    for f in ${reads}; do
        if [[ "\$f" == *_R1* ]]; then
            sample=\$(basename "\$f" | sed 's/_R1.*//')
            r2=\$(echo "\$f" | sed 's/_R1/_R2/')
            echo "\${sample},\${f},\${r2}" >> samplesheet.csv
        fi
    done
    """

    stub:
    """
    echo "sample,fastq_1,fastq_2" > samplesheet.csv
    echo "sample1,sample1_R1.fastq.gz,sample1_R2.fastq.gz" >> samplesheet.csv
    """
}
