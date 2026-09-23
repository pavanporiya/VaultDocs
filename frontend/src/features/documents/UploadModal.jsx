import React, { useState } from 'react';
import { Modal, Button, useToast } from '../../shared/components';
import apiClient from '../../shared/services/apiClient';
import { Upload } from 'lucide-react';
import { formatFileSize } from '../../shared/utils/format';

/**
 * Shared Upload / Replace File modal.
 *
 * Uses the real backend behavior: both initial upload (POST) and replacement
 * (PUT) hit `/documents/{id}/upload`; the backend versions the file
 * automatically. `mode` only changes the copy, never invents an endpoint.
 *
 * Props:
 * - document: the target document record
 * - mode: 'POST' (first upload) | 'PUT' (replace)
 * - onClose: called after close
 * - onUploaded: called with the updated document after a successful upload
 */
export const UploadModal = ({ isOpen, document, mode = 'POST', onClose, onUploaded }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const toast = useToast();

  const isReplace = mode === 'PUT';

  const handleClose = () => {
    setSelectedFile(null);
    onClose();
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile || !document?.id) {
      toast.error('Please select a file to upload.', 'Validation Error');
      return;
    }

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const endpoint = `/documents/${document.id}/upload`;
      const updatedDoc =
        isReplace === true
          ? await apiClient.put(endpoint, formData)
          : await apiClient.upload(endpoint, formData);

      toast.success(
        isReplace
          ? `Replaced file for "${document.name}" — new version created.`
          : `File uploaded for "${document.name}".`
      );

      setSelectedFile(null);
      if (onUploaded) {
        onUploaded(updatedDoc || document);
      }
      onClose();
    } catch (err) {
      toast.error(err.message || 'File upload failed.', 'Upload Error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={
        isReplace
          ? `Replace File (New Version) — ${document?.name || ''}`
          : `Upload File — ${document?.name || ''}`
      }
      size="sm"
    >
      <form onSubmit={handleFileUpload} className="vd-form">
        <div className="vd-file-input-group">
          <label className="vd-file-label" htmlFor="vd-upload-file-input">
            Select File to Upload
          </label>
          <input
            id="vd-upload-file-input"
            type="file"
            className="vd-file-input"
            onChange={(e) => setSelectedFile(e.target.files[0] || null)}
            required
            disabled={submitting}
          />
          {selectedFile && (
            <span className="vd-selected-file-info">
              Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
            </span>
          )}
        </div>
        {isReplace && (
          <span className="vd-replace-note">
            Uploading a replacement file creates a new document version automatically while
            preserving historical versions.
          </span>
        )}
        <div className="vd-modal-footer">
          <Button variant="secondary" type="button" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            icon={Upload}
            loading={submitting}
            disabled={!selectedFile}
          >
            {isReplace ? 'Upload Replacement' : 'Upload File'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

export default UploadModal;
