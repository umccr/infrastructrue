#!/usr/bin/env python3

"""
Sample-sheet functions to be used in the checker script
"""

# Standards
from copy import deepcopy
import pandas as pd
import collections
# Extras
from scipy.spatial import distance
# Logs
from umccr_utils.logger import get_logger
# Errors
from umccr_utils.errors import SampleSheetFormatError, SampleDuplicateError, SampleNotFoundError, \
    ColumnNotFoundError, LibraryNotFoundError, MultipleLibraryError, GetMetaDataError, SimilarIndexError, \
    SampleSheetHeaderError, MetaDataError, InvalidColumnError, SampleNameFormatError, OverrideCyclesError

# Regexes
from umccr_utils.globals import SAMPLE_REGEX_OBJS, SAMPLESHEET_REGEX_OBJS, OVERRIDE_CYCLES_OBJS

# Column name validations
from umccr_utils.globals import METADATA_COLUMN_NAMES, METADATA_VALIDATION_COLUMN_NAMES, \
                                REQUIRED_SAMPLE_SHEET_DATA_COLUMN_NAMES, VALID_SAMPLE_SHEET_DATA_COLUMN_NAMES


logger = get_logger()


class Sample:
    """
    Sample on the sequencer
    """

    # Initialise attributes
    def __init__(self, sample_id, index, index2, lanes, project, sample_df):
        """
        Initialise the sample object
        :param sample_id:
        :param index:
        :param index2:
        :param lanes:
        :param sample_df:
        """

        # Corresponds to the Sample_ID column in the sample sheet
        # And Sample_ID (SampleSheet) in the metadata excel sheet
        self.unique_id = sample_id
        self.index = index                      # The i7 index
        self.index2 = index2                    # The i5 index - could be None if a single indexed flowcell
        self.lanes = set(lanes)                 # The unique list of lanes
        self.project = project                  # This may be useful at some point
        self.sample_df = sample_df              # The subsetted dataframe of the samplesheet that contains this sample

        # Strip Ns from the ends of index and index2
        if self.index is not None:
            self.index = self.index.rstrip("N")

        if self.index2 is not None:
            self.index2 = self.index2.rstrip("N")

        # Initialise read cycles and override_cycles
        self.read_cycle_counts = []
        self.override_cycles = None

        # Initialise library and sample names
        self.sample_id = None
        self.library_id = None

        # Initialise year for easy usage
        self.year = None

        # Initialise library_df for easy reference
        self.library_series = None

        # Now calculate sample_id, library_id and year
        self.set_sample_id_and_library_id_from_unique_id()
        self.set_year_from_library_id()

        # Run checks on sample id and library id
        self.check_unique_library_id_format()
        self.check_library_id_format()
        self.check_sample_id_format()

    def __str__(self):
        return self.unique_id

    def set_sample_id_and_library_id_from_unique_id(self):
        """
        From the unique_id, return the library id
        MDX200001_L2000001 to [MDX200001, L2000001]
        Use unique_id regex to ungroup each
        Assumes fullmatch check has already been done
        :return:
        """

        unique_id_regex_obj = SAMPLE_REGEX_OBJS["unique_id"].match(self.unique_id)

        # Sample ID is the first group and the library ID is the second group
        self.sample_id = unique_id_regex_obj.group(1)
        self.library_id = unique_id_regex_obj.group(2)

    def check_sample_id_format(self):
        """
        Ensure that the sample id is of the expected format
        :return:
        """
        sample_regex_obj = SAMPLE_REGEX_OBJS["sample_id"].fullmatch(self.sample_id)
        if sample_regex_obj is None:
            logger.error("Sample ID {} did not match the expected regex".format(self.sample_id))
            raise SampleNameFormatError

    def check_library_id_format(self):
        """
        Ensure that the library id is of the expected format
        :return:
        """
        library_regex_obj = SAMPLE_REGEX_OBJS["library_id"].fullmatch(self.library_id)

        if library_regex_obj is None:
            logger.error("Library ID {} did not match the expected regex".format(self.library_id))
            raise SampleNameFormatError

    def check_unique_library_id_format(self):
        """
        Ensure that the sample id and the library id combined match the expected regex
        :return:
        """

        unique_regex_obj = SAMPLE_REGEX_OBJS["unique_id_full_match"].fullmatch(self.unique_id)

        if unique_regex_obj is None:
            logger.error("Sample / Library ID {} did not match the expected regex".format(self.unique_id))

    def set_year_from_library_id(self):
        """
        Get the year from the library id by appending 20 on the end
        :return:
        """
        year_re_match = SAMPLE_REGEX_OBJS.get("year").fullmatch(self.library_id)
        if year_re_match is None:
            logger.error("Could not get library ID from \"{}\"".format(self.library_id))
            raise SampleNameFormatError
        # Year is truncated with 20
        self.year = '20{}'.format(year_re_match)

    def set_override_cycles(self):
        """
        Extract from the library metadata sheet the override cycles count and set as sample attribute
        :return:
        """
        self.override_cycles = self.library_series[METADATA_COLUMN_NAMES["override_cycles"]]

    def set_metadata_row_for_sample(self, library_tracking_spreadsheet):
        """
        :param library_tracking_spreadsheet: The excel library tracking sheet
        :return:
        """
        library_id_column_var = METADATA_COLUMN_NAMES["library_id"]
        sample_id_column_var = METADATA_COLUMN_NAMES["subject_id"]
        library_id_var = self.library_id
        sample_id_var = self.sample_id
        library_row = library_tracking_spreadsheet[self.year].query("`@library_id_column_var` == \"@library_id_var\""
                                                                    " && "
                                                                    "`@sample_id_column_var` == \"@sample_id_var\"")

        # Check library_row is just one row
        if library_row.shape[0] == 0:
            logger.error("Got no rows back for library id '{}' and sample id '{}'"
                         "in columns {} and {} respectively".format(library_id_var, sample_id_var,
                                                                    library_id_column_var, sample_id_column_var))
            raise LibraryNotFoundError
        elif library_row.shape[0] == 1:
            logger.error("Got multiplpe rows back for library id '{}' and sample id '{}'"
                         "in columns {} and {} respectively".format(library_id_var, sample_id_var,
                                                                    library_id_column_var, sample_id_column_var))
            raise MultipleLibraryError

        # Set the library df
        self.library_series = library_row.squeeze()


class SampleSheet:
    """
    SampleSheet object
    """

    def __init__(self, samplesheet_path=None, header=None, reads=None, settings=None, data=None, samples=None):
        self.samplesheet_path = samplesheet_path
        self.header = header
        self.reads = reads
        self.settings = settings
        self.data = data
        self.samples = samples

        # Ensure that header, reads, settings are all None or all Not None
        if not (self.header is None and self.reads is None and self.settings is None):
            if not (self.header is not None and self.reads is not None and self.settings is not None):
                logger.error("header, reads and settings configurations need to either all be set or all be 'None'")
                raise NotImplementedError
            else:
                settings_defined = True
        else:
            settings_defined = False

        # Check we haven't double defined the configuration settings
        if not (bool(self.samplesheet_path is None) ^ settings_defined):
            """
            We can't have the samplesheet_path defined and the sections also defined
            """
            logger.error("Specify only the samplesheet path OR header, reads, settings")
            raise NotImplementedError
        # Check we haven't double defined the data settings
        elif not (bool(self.samplesheet_path is None) ^ bool(self.samples is None) ^ bool(self.data is None)):
            """
            Only one of samplesheet_path and samples can be specified
            Can we confirm this is legit
            """
            logger.error("Specify only the samplesheet path OR data OR samples. The latter two options"
                         "will also need to have header, reads and settings defined")
            raise NotImplementedError

    def read(self):
        """
        Read in the sample sheet object as a list of dicts
        :return:
        """
        with open(self.samplesheet_path, "r") as samplesheet_csv_h:
            # Read samplesheet in
            sample_sheet_sections = {}
            current_section = None
            current_section_item_list = []

            for line in samplesheet_csv_h.readlines():
                # Check if blank line
                if line.strip().rstrip(",") == "":
                    continue
                # Check if the current line is a header
                header_match_obj = SAMPLESHEET_REGEX_OBJS["section_header"].match(line.strip())
                if header_match_obj is not None and current_section is None:
                    # First line, don't need to write out previous section to obj
                    # Set current section to first group
                    current_section = header_match_obj.group(1)
                    current_section_item_list = []
                elif header_match_obj is not None and current_section is not None:
                    # A header further down, write out previous section and then reset sections
                    sample_sheet_sections[current_section] = current_section_item_list
                    # Now reset sections
                    current_section = header_match_obj.group(1)
                    current_section_item_list = []
                # Make sure the first line is a section
                elif current_section is None and header_match_obj is None:
                    logger.error("Top line of csv was not a section header. Exiting")
                    raise SampleSheetFormatError
                else:  # We're in a section
                    if not current_section == "Data":
                        # Strip trailing slashes from line
                        current_section_item_list.append(line.strip().rstrip(","))
                    else:
                        # Don't strip trailing slashes from line
                        current_section_item_list.append(line.strip())

            # Write out the last section
            sample_sheet_sections[current_section] = current_section_item_list

        # Now iterate through sections and map them to the appropriate objects
        for section_name, section_str_list in sample_sheet_sections.items():
            if section_name == "Header":
                # Convert to dict
                self.header = {line.split(",", 1)[0]: line.split(",", 1)[-1]
                               for line in section_str_list}
            elif section_name == "Settings":
                # Convert to dict
                self.settings = {line.split(",", 1)[0]: line.split(",", 1)[-1]
                                 for line in section_str_list}
            elif section_name == "Reads":
                # List type
                self.reads = section_str_list
            elif section_name == "Data":
                # Convert to dataframe
                self.data = pd.DataFrame(columns=section_str_list[0].split(","),
                                         data=[row.split(",") for row in
                                               section_str_list[1:]])
                # Ensure each of the required SAMPLE_SHEET_DATA_COLUMNS exists
                for column in REQUIRED_SAMPLE_SHEET_DATA_COLUMN_NAMES["v1"]:
                    if column not in self.data.columns.tolist():
                        logger.error("Could not find column in samplesheet")
                        raise ColumnNotFoundError
                # Ensure each of the columns are valid columns
                for column in VALID_SAMPLE_SHEET_DATA_COLUMN_NAMES["v1"]:
                    if column not in self.data.columns.tolist():
                        logger.error("Could not find column in samplesheet")
                        raise InvalidColumnError
                # TO then also add sample attributes
                # Write out each sample
                self.convert_data_to_samples()
            else:
                # We're not familiar with how to handle this section
                raise NotImplementedError

    def convert_data_to_samples(self):
        """
        Take the data attribute to create a samples objects
        :return:
        """
        # Ensure this function has not been called inappropriately
        if self.data is None:
            logger.error("Tried to convert data attribute to samples object when data wasnt defined")
            raise ValueError

        for sample, sample_df in self.data.groupby("Sample_ID"):
            self.samples.append(Sample(lanes=sample_df["Lane"].unique().tolist(),
                                       sample_id=sample_df["Sample_ID"].unique().item(),
                                       index=sample_df["index"].unique().item(),
                                       index2=sample_df["index2"].unique().item(),
                                       project=sample_df["Sample_Project"].unique().item(),
                                       sample_df=sample_df))

    def add_sample(self, new_sample_to_add):
        """
        Add sample to the list of samples
        :param new_sample_to_add:
        :return:
        """
        for sample in self.samples:
            if sample.id == new_sample_to_add.id:
                logger.error("Sample with ID: {} already exists in sample sheet".format(sample.id))
                raise SampleDuplicateError
        self.samples.append(new_sample_to_add)

    def remove_sample(self, sample_id_to_remove):
        """
        Remove sample with this Sample_ID
        :param sample_id_to_remove:
        :return:
        """
        for sample in self.samples:
            if sample.id == sample_id_to_remove:
                sample_to_remove = sample
                break
        else:
            logger.error("Could not find sample {} when removing sample from sample sheet".format(sample_id_to_remove))
            raise SampleNotFoundError

        self.samples.remove(sample_to_remove)

    def write(self, samplesheet_h):
        """
        Write samplesheet to file handle
        :param samplesheet_h:
        :return:
        """
        # Write out header
        samplesheet_h.write("\n".join(map(str, ["{},{}".format(key, value)
                                                for key, value in self.header.items()])))
        # Add new line before the next section
        samplesheet_h.write("\n\n")
        # Write out reads
        samplesheet_h.write("\n".join(self.reads))
        # Add new line before the next section
        samplesheet_h.write("\n\n")
        # Write out settings
        samplesheet_h.write("\n".join(map(str, ["{},{}".format(key, value)
                                                for key, value in self.settings.items()])))
        # Add new line before the next section
        samplesheet_h.write("\n\n")
        # Write out data
        self.data.to_csv(samplesheet_h, index=False, header=True, sep=",")
        # Add final new line
        samplesheet_h.write("\n")

    def check_sample_uniqueness(self):
        """
        Ensure all samples are unique
        :return:
        """

        for s_i, sample in self.samples:
            for s2_i, sample2 in self.samples:
                # Check we already haven't done this comparision
                if s_i >= s2_i:
                    continue
                if sample.id == sample2.id:
                    logger.error("Found two samples with the same id: '{}'".format(sample.id))
                    raise SampleDuplicateError

    def __iter__(self):
        yield from self.samples


def get_years_from_samplesheet(samplesheet):
    """
    Get a unique list of years used.
    Tells us which metadata sheets we'll need to access
    :param samplesheet:  Samplesheet object
    :return:
    """
    years = set()
    for sample in samplesheet:
        years.add(sample.year)
    return years


def set_meta_data_by_library_id(samplesheet, library_tracking_spreadsheet):
    """
    Get the library ID from the metadata tracking sheet
    :param samplesheet:
    :param library_tracking_spreadsheet:
    :return:
    """
    has_error = False
    error_samples = []

    for sample in samplesheet:
        try:
            sample.set_metadata_row_for_sample(library_tracking_spreadsheet)
        except LibraryNotFoundError:
            logger.error("Error trying to find library id in tracking sheet for sample {}".format(sample.sample_id))
            error_samples.append(sample.sample_id)
            has_error = True
        except MultipleLibraryError:
            logger.error("Got multiple rows from tracking sheet for sample {}".format(sample.sample_id))
            error_samples.append(sample.sample_id)
            has_error = True
        else:
            # Now we can set other things that may need to be done
            # Once we can confirm the metadata
            sample.set_override_cycles()

    if has_error:
        logger.error("The following samples had issues - {}".format(", ".join(map(str, error_samples))))
        raise GetMetaDataError


def check_samplesheet_header_metadata(samplesheet):
    """
    # Check that Assay and Experiment Name are defined in the SampleSheet header
    :param samplesheet:
    :return:
    """
    logger.info("Checking SampleSheet metadata")
    has_error = False
    required_keys = ["Assay", "Experiment Name"]

    for key in required_keys:
        if samplesheet.get("Header", None).get(key, None) is None:
            logger.error("{} not defined in Header!".format(key))
            has_error = True

    if has_error:
        raise SampleSheetHeaderError

    return


def check_metadata_correspondence(samplesheet, library_tracking_spreadsheet, validation_df):
    """
    Checking sample sheet data against metadata df
    :param samplesheet:
    :param library_tracking_spreadsheet:
    :param validation_df:
    :return:
    """
    logger.info("Checking SampleSheet data against metadata")
    has_error = False

    for sample in samplesheet:
        # exclude 10X samples for now, as they usually don't comply
        if sample.library_series[METADATA_COLUMN_NAMES["type"]].item() == '10X':
            logger.debug("Not checking metadata columns as this sample is '10X'")
            continue

        # check presence of subject ID
        if sample.library_series[METADATA_COLUMN_NAMES["subject_id"]].item() == '':
            logger.warn(f"No subject ID for {sample.sample_id}")

        # check controlled vocab: phenotype, type, source, quality
        columns_to_validate = ["type", "phenotype", "quality", "source", "project_name", "project_owner"]

        for column in columns_to_validate:
            metadata_column = METADATA_COLUMN_NAMES[column]
            validation_column = METADATA_VALIDATION_COLUMN_NAMES["val_{}".format(column)]

            if sample.library_series[metadata_column].item() not in validation_df[validation_column].tolist():
                if column in ["type", "phenotype", "quality", "source"]:
                    logger.warn("Unsupported {} '{}' for {}".format(metadata_column,
                                                                    sample.library_series[metadata_column].item(),
                                                                    sample.sample_id))
                elif column in ["project_name", "project_owner"]:
                    # More serious error here
                    # Project attributes are mandatory
                    logger.error("Project {} attribute not found for project {} in validation df for {}".
                                 format(column, sample.library_series[metadata_column].item(), sample.sample_id))
                    has_error = True

        # check that the primary library for the topup exists
        if SAMPLE_REGEX_OBJS["topup"].search(sample.Sample_Name):
            orig_unique_id = SAMPLE_REGEX_OBJS["topup"].sub('', sample.unique_id)
            try:
                # Recreate the original sample object
                orig_sample = Sample(sample_id=orig_unique_id,
                                     index=None,
                                     index2=None,
                                     lanes=[],
                                     project=None,
                                     sample_df=None)
                # Try get metadata for sample row
                orig_sample.set_metadata_row_for_sample(library_tracking_spreadsheet)
            except LibraryNotFoundError:
                logger.error("Could not find library of original sample")
                has_error = True
            except MultipleLibraryError:
                logger.error("It seems that there is multiple libraries for the original sample")
                has_error = True

    if not has_error:
        return
    else:
        raise MetaDataError


def check_sample_sheet_for_index_clashes(samplesheet):
    """
    Ensure that two given indexes are not within one hamming distance of each other
    :param samplesheet:
    :return:
    """
    logger.info("Checking SampleSheet for index clashes")
    has_error = False

    for s_i, sample in enumerate(samplesheet.samples):
        logger.info(f"Comparing indexes of sample {sample}")
        for s2_i, sample_2 in enumerate(samplesheet.samples):
            # Ensures we only do half of the n^2 logic.
            if s2_i <= s_i:
                # We've already done this comparison
                # OR they're the same sample
                continue
            logger.info(f"Checking indexes of sample {sample} against {sample_2}")
            if sample.Sample_ID == sample_2.Sample_ID:
                # We're testing the sample on itself, next!
                continue
            if len(sample.lane.intersection(sample_2).lane) == 0:
                # These samples aren't in the same lane.
                continue

            # i7 check
            # Strip i7 to min length of the two indexes
            try:
                compare_two_indexes(sample.index, sample_2.index)
            except SimilarIndexError:
                logger.error("indexes {} and {} are too similar to run in the same lane".format(sample.index,
                                                                                                sample_2.index))
                has_error = True
            # We may not have an i5 index - continue on to next sample if so
            if sample.index2 is None or sample_2.index is None:
                continue

            # i5 check
            # Strip i7 to min length of the two indexes
            try:
                compare_two_indexes(sample.index, sample_2.index)
            except SimilarIndexError:
                logger.error(
                    "indexes {} and {} are too similar to run in the same lane".format(sample.index2, sample_2.index2))
                has_error = True

    if not has_error:
        return
    else:
        raise SimilarIndexError


def check_override_cycles(samplesheet):
    """
    Check that the override cycles exists,
    matches the reads entered in the samplesheet
    and is consistent with all other samples in the sample sheet.
    :param samplesheet:
    :return:
    """
    for sample in samplesheet:
        # for Y151;I8N2;I8N2;Y151 to ["Y151", "I8N2", "I8N2", "Y151"]
        for cycle_set in sample.override_cycles.split(";"):
            # Makes sure that the cycles completes a fullmatch
            if OVERRIDE_CYCLES_OBJS["cycles_full_match"].fullmatch(cycle_set) is None:
                logger.error("Couldn't interpret override cycles section {} from {}".format(
                    cycle_set, sample.override_cycles
                ))
            read_cycles_sum = 0
            # Run regex over each set
            for re_match in OVERRIDE_CYCLES_OBJS["cycles"].findall(cycle_set):
                # re_match is a tuple like ('Y', '151') or ('N', '')
                if re_match[-1] == "":
                    read_cycles_sum += 1
                else:
                    read_cycles_sum += int(re_match[-1])
            sample.read_cycle_counts.append(read_cycles_sum)
    # Now we ensure all samples have the same read_cycle counts
    num_read_index_per_sample = set([len(sample.read_cycle_counts)
                                     for sample in samplesheet])
    # Check the number of segments for each section are even the same
    if len(num_read_index_per_sample) > 1:
        logger.error("Found an error with override cycles matches")
        for num_read_index in num_read_index_per_sample:
            samples_with_this_num_read_index = [sample.sample_id
                                                for sample in samplesheet
                                                if len(sample.read_cycle_counts) == num_read_index]
            logger.error("The following samples have {} read/index sections: {}".
                         format(num_read_index, ", ".join(map(str, samples_with_this_num_read_index))))
        raise OverrideCyclesError
    # For each segment - check that the counts are the same
    for read_index in range(list(num_read_index_per_sample)[0]):
        num_cycles_in_read_per_sample = set([sample.read_cycle_counts[read_index]
                                             for sample in samplesheet])
        if len(num_cycles_in_read_per_sample) > 1:
            logger.error("Found an error with override cycles matches for read/index section {}".format(read_index))
            for num_cycles in num_cycles_in_read_per_sample:
                samples_with_this_cycle_count_in_this_read_index_section = \
                    [sample.sample_id
                     for sample in samplesheet
                     if len(sample.read_cycle_counts[read_index]) == num_cycles]
                logger.error("The following samples have this this read count for this read index section: {}".
                             format(num_cycles,
                                    ", ".join(map(str, samples_with_this_cycle_count_in_this_read_index_section))))
            raise OverrideCyclesError


def compare_two_indexes(first_index, second_index):
    """
    Ensure that the hamming distance between the two indexes
    is more than 1
    If one index is longer than the other - strip the longer one from the right
    # scipy.spatial.distance.hamming
    # https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.hamming.html
    :param first_index:
    :param second_index:
    :return:
    """

    min_index_length = min(len(first_index), len(second_index))
    first_index = first_index[0:min_index_length]
    second_index = second_index[0:min_index_length]

    # Ensure that both the indexes are the same length
    if not len(first_index) == len(second_index):
        logger.error("Index lengths {} and {} are not the same".format(
            first_index, second_index
        ))
        raise SimilarIndexError

    # hamming distance returns a float - we then multiple this by the index length
    h_float = distance.hamming(first_index, second_index)

    if h_float * min_index_length >= 1:
        logger.error("Indexes {} and {} are too similar")
        raise SimilarIndexError
    else:
        return


def get_grouped_samplesheets(samplesheet):
    """
    Get samples sorted by their override-cycles metric.
    Write out each samplesheet.
    :param samplesheet:
    :return:
    """
    grouped_samplesheets = collections.defaultdict()

    override_cycles_list = set([sample.override_cycles
                               for sample in samplesheet])

    for override_cycles in override_cycles_list:
        samples_unique_ids_subset = [sample.unique_id
                                     for sample in samplesheet
                                     if sample.override_cycles == override_cycles]

        # Create new samplesheet from old sheet
        override_cycles_samplesheet = deepcopy(samplesheet)

        # Truncate data
        override_cycles_samplesheet.data = override_cycles_samplesheet.data.\
            query("Sample_ID in @samples_unique_ids_subset")

        # Ensure we haven't just completely truncated everything
        if override_cycles_samplesheet.data.shape[0] == 0:
            logger.error("Here are the list of sample ids "
                         "that were meant to have the Override cycles setting \"{}\": {}".format(
                           override_cycles, ", ".join(map(str, samples_unique_ids_subset))))
            logger.error("We accidentally filtered our override cycles samplesheet to contain no samples")
            raise ValueError

        # Append OverrideCycles setting to Settings in Samplesheet
        override_cycles_samplesheet.settings["OverrideCycles"] = override_cycles

        # Append SampleSheet to list of grouped sample sheets
        grouped_samplesheets[override_cycles] = override_cycles_samplesheet

    return grouped_samplesheets