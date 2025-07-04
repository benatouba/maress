# Incubator Template

Welcome to the [NFDI4Earth](https://www.nfdi4earth.de/) community!

This template is designed to assist you in adhering to the FAIR principles and showcasing your project within the NFDI4Earth community.

## Getting Started

**Step 1**: Get acess to the RWTH-AACHEN GitLab! Use a browser to access https://git.rwth-aachen.de and login either via the DFN AAI Single Sign-On if your institution supports this, or authenticate via Github (if you don't have DFN Login and no Github accound, please create an account under https://github.com/ and use this one). After you have initially logged in once into the RWTH Aachen Gitlab, send an email with your account name and the name of your Pilot to nfdi4earth-incubators@tu-dresden.de. You will then be granted access rights to the Gitlab project for your Pilot.

**Step 2**:
Adapt the meta files, specifically the _nfdi4earth-meta.yaml_ and the _CITATION.cff_, to ensure the findability of your project. _nfdi4earth-meta.yaml_ is used to collect all metadata on your research project itself and the produced outcomes. _CITATION.cff_ is used to collect metadata on one specific software and make it citable. You can either use this Gitlab project to host your software source code or if you are committing to an existing, external code repository please make sure there is a _CITATION.cff_ and add the link to the _nfdi4earth-meta.yaml_. You can make the changes using the WEB-IDE or by [cloning](https://docs.gitlab.com/ee/tutorials/make_first_git_commit/) this repository.

**Step 3**:
Update the _README.md_ and _lhb-article.md_ files.
Initially, both files will be identical, but they may diverge as your project progresses. The content of the _lhb-article.md_ will be highligthed through the [Living Handbook (LHB)](https://nfdi4earth.pages.rwth-aachen.de/livinghandbook/livinghandbook/#N4E_Pilots/). Begin by addressing the TODO items in the _lhb-article.md_, copying your proposal text to both files, and adapting links and headings using [Markdown syntax](https://www.markdownguide.org/basic-syntax/). Later, the Living Handbook Article should providen an easy-to-understand overview of the project and your results. In contrast, the _README.md_ may also be part of your final project report and for software projects, the _README.md_ should highlight how to install and use the software.

## References

Checkout the [GitLab repositories](https://git.rwth-aachen.de/nfdi4earth/pilotsincubatorlab) and [LHB articles](https://nfdi4earth.pages.rwth-aachen.de/livinghandbook/livinghandbook/) of other (already completed) NFDI4Earth projects to get a sense of how to design your the README and article. Utilize the feature to evaluate repositories that serve as sources of inspiration.

## Funding

This work has been funded by the German Research Foundation (NFDI4Earth,
DFG project no. 460036893, https://www.nfdi4earth.de/).

# MaRESS

## **Ma**pping **R**esearch in **E**arth **S**ystem **S**ciences

Application for Ecological Data Integration and AI-Assisted Information Management

The application is developed in the course of an incubator program by NFDI4Earth by scientists from Technische
Universität Berlin.

## Currently we are planning to implement the following features:
- **Research Data Mapping**: Visualize and manage research data in a graph-based interface with connections of research papers, datasets, and other resources.
- **Geospatial Mapping**: Create and manage geospatial features of your research data in a map-based interface.
- **AI-Assisted Information Management**: Use AI to assist in the management and analysis of research data, including automated tagging, summarization, and recommendation of related resources.
- **Semantic Mapping**: Information retrieval and semantic search capabilities based on text processing and metadata extraction.
